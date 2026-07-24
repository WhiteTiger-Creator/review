#include "qr_composer.h"

#include <string.h>

/* Matrix stage: function patterns, data placement, mask application, and
 * format/version information per matrix-placement.md. */

static void set_mod(qrt_matrix *m, int r, int c, int v) {
    m->grid[r][c] = (uint8_t)v;
    m->func[r][c] = 1;
}

static void draw_finder(qrt_matrix *m, int r0, int c0) {
    for (int dr = -1; dr <= 7; dr++) {
        for (int dc = -1; dc <= 7; dc++) {
            int r = r0 + dr, c = c0 + dc;
            if (r < 0 || r >= m->size || c < 0 || c >= m->size) continue;
            int ar = dr - 3 < 0 ? 3 - dr : dr - 3;
            int ac = dc - 3 < 0 ? 3 - dc : dc - 3;
            int dist = ar > ac ? ar : ac;
            set_mod(m, r, c, (dist != 2 && dist != 4) ? 1 : 0);
        }
    }
}

int qrt_version_info_bits(int version) {
    int rem = version;
    for (int i = 0; i < 12; i++) rem = (rem << 1) ^ ((rem >> 11) * 0x1F25);
    return (version << 12) | rem;
}

void qrt_build_function_grid(int version, qrt_matrix *m) {
    int size = qrt_symbol_size(version);
    memset(m, 0, sizeof(*m));
    m->size = size;

    draw_finder(m, 0, 0);
    draw_finder(m, 0, size - 7);
    draw_finder(m, size - 7, 0);

    for (int i = 8; i < size - 8; i++) {
        int v = (i % 2 == 0) ? 1 : 0;
        set_mod(m, 6, i, v);
        set_mod(m, i, 6, v);
    }

    const int *centers = qrt_alignment_centers[version];
    for (int a = 0; centers[a] >= 0; a++) {
        for (int b = 0; centers[b] >= 0; b++) {
            int cy = centers[a], cx = centers[b];
            if ((cy <= 8 && cx <= 8) || (cy <= 8 && cx >= size - 9) || (cy >= size - 9 && cx <= 8))
                continue;
            for (int dr = -2; dr <= 2; dr++) {
                for (int dc = -2; dc <= 2; dc++) {
                    int ar = dr < 0 ? -dr : dr;
                    int ac = dc < 0 ? -dc : dc;
                    int dist = ar > ac ? ar : ac;
                    set_mod(m, cy + dr, cx + dc, dist != 1 ? 1 : 0);
                }
            }
        }
    }

    for (int i = 0; i < 9; i++) {
        if (i < size && !m->func[8][i]) set_mod(m, 8, i, 0);
        if (i < size && !m->func[i][8]) set_mod(m, i, 8, 0);
    }
    for (int i = 0; i < 8; i++) {
        if (!m->func[8][size - 1 - i]) set_mod(m, 8, size - 1 - i, 0);
        if (!m->func[size - 1 - i][8]) set_mod(m, size - 1 - i, 8, 0);
    }
    set_mod(m, size - 8, 8, 1);

    if (version >= 7) {
        int vinfo = qrt_version_info_bits(version);
        for (int i = 0; i < 18; i++) {
            int bit = (vinfo >> i) & 1;
            int a = size - 11 + i % 3;
            int b = i / 3;
            set_mod(m, b, a, bit);
            set_mod(m, a, b, bit);
        }
    }
}

void qrt_place_data(qrt_matrix *m, const uint8_t *stream, int stream_len, int version) {
    int size = m->size;
    int total_bits = stream_len * 8 + qrt_remainder_bits[version];
    int bit_index = 0;
    int right = size - 1;
    while (right >= 1) {
        if (right == 6) right = 5;
        for (int vert = 0; vert < size; vert++) {
            for (int j = 0; j < 2; j++) {
                int c = right - j;
                int upward = ((right + 1) & 2) == 0;
                int r = upward ? size - 1 - vert : vert;
                if (!m->func[r][c] && bit_index < total_bits) {
                    int bit = 0;
                    if (bit_index < stream_len * 8)
                        bit = (stream[bit_index >> 3] >> (7 - (bit_index & 7))) & 1;
                    m->grid[r][c] = (uint8_t)bit;
                    bit_index++;
                }
            }
        }
        right -= 2;
    }
    if (bit_index != total_bits) qrt_die("placement consumed %d of %d bits", bit_index, total_bits);
}

int qrt_mask_condition(int mask, int r, int c) {
    switch (mask) {
        case 0: return (r + c) % 2 == 0;
        case 1: return r % 2 == 0;
        case 2: return c % 3 == 0;
        case 3: return (r + c) % 3 == 0;
        case 4: return (r / 2 + c / 3) % 2 == 0;
        case 5: return (r * c) % 2 + (r * c) % 3 == 0;
        case 6: return ((r * c) % 2 + (r * c) % 3) % 2 == 0;
        default: return ((r + c) % 2 + (r * c) % 3) % 2 == 0;
    }
}

int qrt_format_info_bits(char level, int mask) {
    int data = (qrt_ecc_format_bits(level) << 3) | mask;
    int rem = data;
    for (int i = 0; i < 10; i++) rem = (rem << 1) ^ ((rem >> 9) * 0x537);
    return ((data << 10) | rem) ^ 0x5412;
}

void qrt_apply_mask_and_format(const qrt_matrix *base, qrt_matrix *out, int mask, char level) {
    memcpy(out, base, sizeof(*out));
    int size = out->size;
    for (int r = 0; r < size; r++)
        for (int c = 0; c < size; c++)
            if (!out->func[r][c] && qrt_mask_condition(mask, r, c)) out->grid[r][c] ^= 1;

    int bits = qrt_format_info_bits(level, mask);
    for (int i = 0; i < 6; i++) out->grid[i][8] = (uint8_t)((bits >> i) & 1);
    out->grid[7][8] = (uint8_t)((bits >> 6) & 1);
    out->grid[8][8] = (uint8_t)((bits >> 7) & 1);
    out->grid[8][7] = (uint8_t)((bits >> 8) & 1);
    for (int i = 9; i < 15; i++) out->grid[8][14 - i] = (uint8_t)((bits >> i) & 1);
    for (int i = 0; i < 8; i++) out->grid[8][size - 1 - i] = (uint8_t)((bits >> i) & 1);
    for (int i = 8; i < 15; i++) out->grid[size - 15 + i][8] = (uint8_t)((bits >> i) & 1);
    out->grid[size - 8][8] = 1;
}

void qrt_matrix_sha256(const qrt_matrix *m, char out[65]) {
    static uint8_t payload[QRT_MAX_SIZE * QRT_MAX_SIZE];
    int n = 0;
    for (int r = 0; r < m->size; r++)
        for (int c = 0; c < m->size; c++) payload[n++] = m->grid[r][c] ? '1' : '0';
    qrt_sha256_hex(payload, (size_t)n, out);
}
