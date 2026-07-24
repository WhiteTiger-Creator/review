#include "qr_composer.h"

#include <stdlib.h>
#include <string.h>

/* Assemble stage: encode segment bitstream, terminator, bit padding, and
 * alternating pad codewords into the full data codeword vector per
 * codeword-assembly.md. Writes /app/state/codewords.tsv. */

extern int qrt_alnum_index(int ch);

typedef struct {
    uint8_t bytes[QRT_MAX_CODEWORDS];
    int bit_len;
} bitbuf;

static void bb_append(bitbuf *b, unsigned value, int width) {
    for (int shift = width - 1; shift >= 0; shift--) {
        int bit = (int)((value >> shift) & 1u);
        int idx = b->bit_len >> 3;
        if (idx >= QRT_MAX_CODEWORDS) qrt_die("bitstream overflow");
        if (bit) b->bytes[idx] |= (uint8_t)(0x80 >> (b->bit_len & 7));
        b->bit_len++;
    }
}

static const unsigned MODE_INDICATOR[3] = {0x1, 0x2, 0x4};

static void encode_segment(bitbuf *b, const char *chunk, int count, int mode, int cci_class) {
    bb_append(b, MODE_INDICATOR[mode], 4);
    bb_append(b, (unsigned)count, qrt_cci_width(mode, cci_class));
    if (mode == QRT_MODE_NUMERIC) {
        for (int i = 0; i < count; i += 3) {
            int g = count - i < 3 ? count - i : 3;
            unsigned val = 0;
            for (int k = 0; k < g; k++) val = val * 10 + (unsigned)(chunk[i + k] - '0');
            static const int width[4] = {0, 4, 7, 10};
            bb_append(b, val, width[g]);
        }
    } else if (mode == QRT_MODE_ALNUM) {
        for (int i = 0; i < count; i += 2) {
            if (count - i >= 2) {
                int a = qrt_alnum_index((unsigned char)chunk[i]);
                int c = qrt_alnum_index((unsigned char)chunk[i + 1]);
                if (a < 0 || c < 0) qrt_die("non-alphanumeric char in alnum segment");
                bb_append(b, (unsigned)(a * 45 + c), 11);
            } else {
                int a = qrt_alnum_index((unsigned char)chunk[i]);
                if (a < 0) qrt_die("non-alphanumeric char in alnum segment");
                bb_append(b, (unsigned)a, 6);
            }
        }
    } else {
        for (int i = 0; i < count; i++) bb_append(b, (unsigned char)chunk[i], 8);
    }
}

int qrt_assemble_payload(const qrt_payload *p, const qrt_plan *plan, uint8_t *out, int *out_len) {
    bitbuf b;
    memset(&b, 0, sizeof(b));
    int pos = 0;
    for (int s = 0; s < plan->segment_count; s++) {
        const qrt_segment *seg = &plan->segments[s];
        encode_segment(&b, p->text + pos, seg->char_count, seg->mode, plan->cci_class);
        pos += seg->char_count;
    }
    if (pos != p->text_len) qrt_die("segment plan does not cover payload %s/%s", p->batch_id, p->payload_id);
    if (b.bit_len != plan->total_bits)
        qrt_die("assembled bits %d != planned bits %d for %s/%s", b.bit_len, plan->total_bits,
                p->batch_id, p->payload_id);

    int cap = qrt_data_capacity_bits(plan->version, p->ecc_level);
    if (b.bit_len > cap) qrt_die("bitstream exceeds capacity for %s/%s", p->batch_id, p->payload_id);
    int term = cap - b.bit_len;
    if (term > 4) term = 4;
    bb_append(&b, 0, term);
    if (b.bit_len % 8) bb_append(&b, 0, 8 - (b.bit_len % 8));
    static const unsigned pads[2] = {0xEC, 0x11};
    int pad_i = 0;
    while (b.bit_len < cap) bb_append(&b, pads[pad_i++ % 2], 8);

    *out_len = cap / 8;
    memcpy(out, b.bytes, (size_t)*out_len);
    return 0;
}

int qrt_cmd_assemble(void) {
    static qrt_payload payloads[QRT_MAX_PAYLOADS];
    int count = qrt_load_payloads(payloads, QRT_MAX_PAYLOADS);

    size_t cap = (size_t)count * (QRT_MAX_CODEWORDS * 2 + 160) + 64;
    char *out = malloc(cap);
    if (!out) qrt_die("out of memory");
    size_t off = 0;
    for (int i = 0; i < count; i++) {
        qrt_plan plan;
        if (qrt_load_plan(payloads[i].batch_id, payloads[i].payload_id, &plan) != 0)
            qrt_die("no plan row for %s/%s", payloads[i].batch_id, payloads[i].payload_id);
        uint8_t data[QRT_MAX_CODEWORDS];
        int len = 0;
        qrt_assemble_payload(&payloads[i], &plan, data, &len);
        char hex[QRT_MAX_CODEWORDS * 2 + 1];
        qrt_hex_encode(data, len, hex);
        off += (size_t)snprintf(out + off, cap - off, "%s\t%s\t%d\t%s\n",
                                payloads[i].batch_id, payloads[i].payload_id, len, hex);
    }
    qrt_write_file(QRT_CODEWORDS_TSV, out, off);
    free(out);
    printf("assembled %d codeword vectors\n", count);
    return 0;
}
