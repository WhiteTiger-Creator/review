#include "qr_composer.h"

#include <stdlib.h>
#include <string.h>

/* Emit stage: rebuild each symbol from persisted state rows only, render the
 * scaled PGM label with quiet zone, and publish the deterministic run manifest
 * /app/output/labels/label-run-manifest.json per manifest-export.md. */

typedef struct {
    char batch_id[QRT_MAX_ID];
    char payload_id[QRT_MAX_ID];
    int slen;
    uint8_t stream[QRT_MAX_CODEWORDS * 2];
    char digest[65];
} stream_row;

extern int qrt_load_streams(stream_row *rows, int max);

static int load_winning_mask(const char *batch_id, const char *payload_id) {
    size_t len = 0;
    char *data = qrt_read_file(QRT_TOURNAMENT_TSV, &len);
    if (!data) qrt_die("missing %s (run run-mask-tournament first)", QRT_TOURNAMENT_TSV);
    int mask = -1;
    char *save = NULL;
    for (char *line = strtok_r(data, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        if (!line[0]) continue;
        char *fields[9];
        if (qrt_split_tsv(line, fields, 9) != 9) qrt_die("bad tournament.tsv row");
        if (strcmp(fields[0], batch_id) != 0 || strcmp(fields[1], payload_id) != 0) continue;
        if (atoi(fields[8]) == 1) {
            mask = atoi(fields[2]);
            break;
        }
    }
    free(data);
    if (mask < 0) qrt_die("no winning mask row for %s/%s", batch_id, payload_id);
    return mask;
}

static void render_pgm(const qrt_matrix *m, const char *path) {
    int scale = qrt_config_module_scale();
    int quiet = qrt_config_quiet_modules();
    if (scale < 1 || quiet < 0) qrt_die("bad render config");
    int dim = (m->size + 2 * quiet) * scale;
    size_t cap = (size_t)dim * dim * 4 + 64;
    char *out = malloc(cap);
    if (!out) qrt_die("out of memory rendering %s", path);
    size_t off = (size_t)snprintf(out, cap, "P2 %d %d 255\n", dim, dim);
    for (int py = 0; py < dim; py++) {
        int my = py / scale - quiet;
        for (int px = 0; px < dim; px++) {
            int mx = px / scale - quiet;
            int dark = my >= 0 && my < m->size && mx >= 0 && mx < m->size && m->grid[my][mx] == 1;
            out[off++] = dark ? '0' : '2';
            if (!dark) {
                out[off++] = '5';
                out[off++] = '5';
            }
            out[off++] = px + 1 < dim ? ' ' : '\n';
        }
    }
    qrt_write_file(path, out, off);
    free(out);
}

int qrt_cmd_emit(void) {
    static qrt_payload payloads[QRT_MAX_PAYLOADS];
    int pcount = qrt_load_payloads(payloads, QRT_MAX_PAYLOADS);
    static stream_row rows[QRT_MAX_PAYLOADS];
    int count = qrt_load_streams(rows, QRT_MAX_PAYLOADS);
    if (count != pcount) qrt_die("stream rows %d != payload rows %d", count, pcount);

    qrt_ensure_dir(QRT_OUTPUT_DIR);

    size_t cap = (size_t)count * 1024 + 512;
    char *json = malloc(cap);
    if (!json) qrt_die("out of memory");
    size_t off = (size_t)snprintf(json, cap, "{\n  \"schema\": \"label-run/1\",\n  \"symbol_count\": %d,\n  \"symbols\": [\n", count);

    for (int i = 0; i < count; i++) {
        qrt_plan plan;
        if (qrt_load_plan(rows[i].batch_id, rows[i].payload_id, &plan) != 0)
            qrt_die("no plan row for %s/%s", rows[i].batch_id, rows[i].payload_id);
        int mask = load_winning_mask(rows[i].batch_id, rows[i].payload_id);

        static qrt_matrix base, final;
        qrt_build_function_grid(plan.version, &base);
        qrt_place_data(&base, rows[i].stream, rows[i].slen, plan.version);
        qrt_apply_mask_and_format(&base, &final, mask, payloads[i].ecc_level);

        char matrix_digest[65];
        qrt_matrix_sha256(&final, matrix_digest);

        char pgm_path[600];
        snprintf(pgm_path, sizeof(pgm_path), "%s/%s-%s.pgm", QRT_OUTPUT_DIR,
                 rows[i].batch_id, rows[i].payload_id);
        render_pgm(&final, pgm_path);

        int e = qrt_ecc_index(payloads[i].ecc_level);
        const qrt_block_spec *spec = &qrt_ecc_blocks[plan.version][e];
        off += (size_t)snprintf(json + off, cap - off,
                                "    {\"batch_id\": \"%s\", \"payload_id\": \"%s\", \"ecc_level\": \"%c\", "
                                "\"version\": %d, \"size\": %d, \"mask\": %d, "
                                "\"segment_count\": %d, \"total_bits\": %d, "
                                "\"ec_per_block\": %d, \"group1_blocks\": %d, \"group1_data_codewords\": %d, "
                                "\"group2_blocks\": %d, \"group2_data_codewords\": %d, "
                                "\"interleaved_sha256\": \"%s\", \"matrix_sha256\": \"%s\", "
                                "\"label_pgm\": \"%s\"}%s\n",
                                rows[i].batch_id, rows[i].payload_id, payloads[i].ecc_level,
                                plan.version, qrt_symbol_size(plan.version), mask,
                                plan.segment_count, plan.total_bits,
                                spec->ec_per_block, spec->g1_blocks, spec->g1_data,
                                spec->g2_blocks, spec->g2_data,
                                rows[i].digest, matrix_digest, pgm_path,
                                i + 1 < count ? "," : "");
    }
    off += (size_t)snprintf(json + off, cap - off, "  ]\n}\n");
    qrt_write_file(QRT_MANIFEST_PATH, json, off);
    free(json);
    printf("emitted %d labels and manifest\n", count);
    return 0;
}
