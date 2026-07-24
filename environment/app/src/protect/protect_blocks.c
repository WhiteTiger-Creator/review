#include "qr_composer.h"

#include <stdlib.h>
#include <string.h>

/* Protect stage: split data codewords into group-1/group-2 blocks and compute
 * per-block Reed-Solomon ECC. Writes /app/state/blocks.tsv. */

typedef struct {
    char batch_id[QRT_MAX_ID];
    char payload_id[QRT_MAX_ID];
    int len;
    uint8_t data[QRT_MAX_CODEWORDS];
} cw_row;

static int load_codewords(cw_row *rows, int max) {
    size_t len = 0;
    char *data = qrt_read_file(QRT_CODEWORDS_TSV, &len);
    if (!data) qrt_die("missing %s (run assemble-codewords first)", QRT_CODEWORDS_TSV);
    int count = 0;
    char *save = NULL;
    for (char *line = strtok_r(data, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        if (!line[0]) continue;
        if (count >= max) qrt_die("too many codeword rows");
        char *fields[4];
        if (qrt_split_tsv(line, fields, 4) != 4) qrt_die("bad codewords.tsv row");
        cw_row *r = &rows[count];
        snprintf(r->batch_id, sizeof(r->batch_id), "%s", fields[0]);
        snprintf(r->payload_id, sizeof(r->payload_id), "%s", fields[1]);
        r->len = atoi(fields[2]);
        int n = qrt_hex_decode(fields[3], r->data, QRT_MAX_CODEWORDS);
        if (n != r->len) qrt_die("codeword hex length mismatch for %s/%s", r->batch_id, r->payload_id);
        count++;
    }
    free(data);
    return count;
}

int qrt_cmd_protect(void) {
    static qrt_payload payloads[QRT_MAX_PAYLOADS];
    int pcount = qrt_load_payloads(payloads, QRT_MAX_PAYLOADS);
    static cw_row rows[QRT_MAX_PAYLOADS];
    int count = load_codewords(rows, QRT_MAX_PAYLOADS);
    if (count != pcount) qrt_die("codeword rows %d != payload rows %d", count, pcount);

    size_t cap = (size_t)count * QRT_MAX_BLOCKS * (QRT_MAX_CODEWORDS + 256) + 64;
    char *out = malloc(cap);
    if (!out) qrt_die("out of memory");
    size_t off = 0;
    for (int i = 0; i < count; i++) {
        qrt_plan plan;
        if (qrt_load_plan(rows[i].batch_id, rows[i].payload_id, &plan) != 0)
            qrt_die("no plan row for %s/%s", rows[i].batch_id, rows[i].payload_id);
        int e = qrt_ecc_index(payloads[i].ecc_level);
        const qrt_block_spec *spec = &qrt_ecc_blocks[plan.version][e];
        int pos = 0;
        int block_index = 0;
        for (int g = 1; g <= 2; g++) {
            int nblocks = g == 1 ? spec->g1_blocks : spec->g2_blocks;
            int dlen = g == 1 ? spec->g1_data : spec->g2_data;
            for (int b = 0; b < nblocks; b++) {
                if (pos + dlen > rows[i].len) qrt_die("block split overruns data for %s/%s", rows[i].batch_id, rows[i].payload_id);
                uint8_t ecc[QRT_MAX_BLOCKS * 32];
                qrt_rs_remainder(rows[i].data + pos, dlen, spec->ec_per_block, ecc);
                char dhex[QRT_MAX_CODEWORDS * 2 + 1];
                char ehex[QRT_MAX_BLOCKS * 64 + 1];
                qrt_hex_encode(rows[i].data + pos, dlen, dhex);
                qrt_hex_encode(ecc, spec->ec_per_block, ehex);
                off += (size_t)snprintf(out + off, cap - off, "%s\t%s\t%d\t%d\t%d\t%s\t%s\n",
                                        rows[i].batch_id, rows[i].payload_id, block_index, g,
                                        dlen, dhex, ehex);
                pos += dlen;
                block_index++;
            }
        }
        if (pos != rows[i].len) qrt_die("block split leaves residue for %s/%s", rows[i].batch_id, rows[i].payload_id);
    }
    qrt_write_file(QRT_BLOCKS_TSV, out, off);
    free(out);
    printf("protected %d payloads\n", count);
    return 0;
}
