#include "qr_composer.h"

#include <stdlib.h>
#include <string.h>

/* Tournament stage: for each interleaved stream build the base matrix, score
 * all eight masks with the four penalty rules, pick the lowest total (lowest
 * mask id on ties), and record every row in /app/state/tournament.tsv. */

typedef struct {
    char batch_id[QRT_MAX_ID];
    char payload_id[QRT_MAX_ID];
    int slen;
    uint8_t stream[QRT_MAX_CODEWORDS * 2];
    char digest[65];
} stream_row;

int qrt_load_streams(stream_row *rows, int max) {
    size_t len = 0;
    char *data = qrt_read_file(QRT_STREAMS_TSV, &len);
    if (!data) qrt_die("missing %s (run interleave-streams first)", QRT_STREAMS_TSV);
    int count = 0;
    char *save = NULL;
    for (char *line = strtok_r(data, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        if (!line[0]) continue;
        if (count >= max) qrt_die("too many stream rows");
        char *fields[5];
        if (qrt_split_tsv(line, fields, 5) != 5) qrt_die("bad streams.tsv row");
        stream_row *r = &rows[count];
        snprintf(r->batch_id, sizeof(r->batch_id), "%s", fields[0]);
        snprintf(r->payload_id, sizeof(r->payload_id), "%s", fields[1]);
        r->slen = atoi(fields[2]);
        int n = qrt_hex_decode(fields[3], r->stream, (int)sizeof(r->stream));
        if (n != r->slen) qrt_die("stream hex mismatch for %s/%s", r->batch_id, r->payload_id);
        snprintf(r->digest, sizeof(r->digest), "%s", fields[4]);
        count++;
    }
    free(data);
    return count;
}

int qrt_run_tournament_for(const qrt_matrix *base, char level, int *out_mask,
                           int scores[8][5]) {
    int best_mask = -1;
    int best_total = 0;
    static qrt_matrix trial;
    for (int mask = 0; mask < 8; mask++) {
        qrt_apply_mask_and_format(base, &trial, mask, level);
        int p1 = qrt_penalty_runs(&trial);
        int p2 = qrt_penalty_blocks(&trial);
        int p3 = qrt_penalty_finder(&trial);
        int p4 = qrt_penalty_balance(&trial);
        int total = p1 + p2 + p3 + p4;
        scores[mask][0] = p1;
        scores[mask][1] = p2;
        scores[mask][2] = p3;
        scores[mask][3] = p4;
        scores[mask][4] = total;
        if (best_mask < 0 || total < best_total) {
            best_mask = mask;
            best_total = total;
        }
    }
    *out_mask = best_mask;
    return 0;
}

int qrt_cmd_tournament(void) {
    static qrt_payload payloads[QRT_MAX_PAYLOADS];
    int pcount = qrt_load_payloads(payloads, QRT_MAX_PAYLOADS);
    static stream_row rows[QRT_MAX_PAYLOADS];
    int count = qrt_load_streams(rows, QRT_MAX_PAYLOADS);
    if (count != pcount) qrt_die("stream rows %d != payload rows %d", count, pcount);

    size_t cap = (size_t)count * 8 * 128 + 64;
    char *out = malloc(cap);
    if (!out) qrt_die("out of memory");
    size_t off = 0;
    for (int i = 0; i < count; i++) {
        qrt_plan plan;
        if (qrt_load_plan(rows[i].batch_id, rows[i].payload_id, &plan) != 0)
            qrt_die("no plan row for %s/%s", rows[i].batch_id, rows[i].payload_id);
        static qrt_matrix base;
        qrt_build_function_grid(plan.version, &base);
        qrt_place_data(&base, rows[i].stream, rows[i].slen, plan.version);
        int mask = -1;
        int scores[8][5];
        qrt_run_tournament_for(&base, payloads[i].ecc_level, &mask, scores);
        for (int mk = 0; mk < 8; mk++) {
            off += (size_t)snprintf(out + off, cap - off,
                                    "%s\t%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n",
                                    rows[i].batch_id, rows[i].payload_id, mk,
                                    scores[mk][0], scores[mk][1], scores[mk][2], scores[mk][3],
                                    scores[mk][4], mk == mask ? 1 : 0);
        }
    }
    qrt_write_file(QRT_TOURNAMENT_TSV, out, off);
    free(out);
    printf("scored mask tournament for %d symbols\n", count);
    return 0;
}
