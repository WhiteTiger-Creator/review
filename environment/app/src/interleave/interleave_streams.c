#include "qr_composer.h"

#include <stdlib.h>
#include <string.h>

/* Interleave stage: merge per-block data and ECC codewords round-robin and
 * record the final transmission stream with its SHA-256 in /app/state/streams.tsv. */

typedef struct {
    int group;
    int dlen;
    int elen;
    uint8_t data[QRT_MAX_CODEWORDS];
    uint8_t ecc[QRT_MAX_BLOCKS * 32];
} blk_t;

typedef struct {
    char batch_id[QRT_MAX_ID];
    char payload_id[QRT_MAX_ID];
    int nblocks;
    blk_t blocks[QRT_MAX_BLOCKS];
} pack_t;

static int load_blocks(pack_t *packs, int max) {
    size_t len = 0;
    char *data = qrt_read_file(QRT_BLOCKS_TSV, &len);
    if (!data) qrt_die("missing %s (run protect-blocks first)", QRT_BLOCKS_TSV);
    int count = 0;
    char *save = NULL;
    for (char *line = strtok_r(data, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        if (!line[0]) continue;
        char *fields[7];
        if (qrt_split_tsv(line, fields, 7) != 7) qrt_die("bad blocks.tsv row");
        pack_t *pk = NULL;
        for (int i = 0; i < count; i++) {
            if (strcmp(packs[i].batch_id, fields[0]) == 0 && strcmp(packs[i].payload_id, fields[1]) == 0) {
                pk = &packs[i];
                break;
            }
        }
        if (!pk) {
            if (count >= max) qrt_die("too many payloads in blocks.tsv");
            pk = &packs[count++];
            snprintf(pk->batch_id, sizeof(pk->batch_id), "%s", fields[0]);
            snprintf(pk->payload_id, sizeof(pk->payload_id), "%s", fields[1]);
            pk->nblocks = 0;
        }
        int idx = atoi(fields[2]);
        if (idx < 0 || idx >= QRT_MAX_BLOCKS) qrt_die("block index out of range");
        blk_t *b = &pk->blocks[idx];
        b->group = atoi(fields[3]);
        b->dlen = atoi(fields[4]);
        int n = qrt_hex_decode(fields[5], b->data, QRT_MAX_CODEWORDS);
        if (n != b->dlen) qrt_die("block data hex mismatch");
        b->elen = qrt_hex_decode(fields[6], b->ecc, (int)sizeof(b->ecc));
        if (b->elen <= 0) qrt_die("block ecc hex mismatch");
        if (idx + 1 > pk->nblocks) pk->nblocks = idx + 1;
    }
    free(data);
    return count;
}

int qrt_interleave_pack(const pack_t *pk, uint8_t *out, int max) {
    int off = 0;
    int max_d = pk->blocks[0].dlen;
    for (int i = 0; i < max_d; i++) {
        for (int b = 0; b < pk->nblocks; b++) {
            if (i < pk->blocks[b].dlen) {
                if (off >= max) qrt_die("interleave overflow");
                out[off++] = pk->blocks[b].data[i];
            }
        }
    }
    for (int b = 0; b < pk->nblocks; b++) {
        for (int i = max_d; i < pk->blocks[b].dlen; i++) {
            if (off >= max) qrt_die("interleave overflow");
            out[off++] = pk->blocks[b].data[i];
        }
    }
    int elen = pk->blocks[0].elen;
    for (int i = 0; i < elen; i++) {
        for (int b = 0; b < pk->nblocks; b++) {
            if (off >= max) qrt_die("interleave overflow");
            out[off++] = pk->blocks[b].ecc[i];
        }
    }
    return off;
}

int qrt_cmd_interleave(void) {
    static pack_t packs[QRT_MAX_PAYLOADS];
    int count = load_blocks(packs, QRT_MAX_PAYLOADS);
    if (count == 0) qrt_die("no block rows found");

    size_t cap = (size_t)count * (QRT_MAX_CODEWORDS * 4 + 256) + 64;
    char *out = malloc(cap);
    if (!out) qrt_die("out of memory");
    size_t off = 0;
    for (int i = 0; i < count; i++) {
        uint8_t stream[QRT_MAX_CODEWORDS * 2];
        int slen = qrt_interleave_pack(&packs[i], stream, (int)sizeof(stream));
        char hex[QRT_MAX_CODEWORDS * 4 + 1];
        char digest[65];
        qrt_hex_encode(stream, slen, hex);
        qrt_sha256_hex(stream, (size_t)slen, digest);
        off += (size_t)snprintf(out + off, cap - off, "%s\t%s\t%d\t%s\t%s\n",
                                packs[i].batch_id, packs[i].payload_id, slen, hex, digest);
    }
    qrt_write_file(QRT_STREAMS_TSV, out, off);
    free(out);
    printf("interleaved %d streams\n", count);
    return 0;
}
