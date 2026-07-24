#include "qr_composer.h"

/* ECC block structure per ISO/IEC 18004 table 9, versions 1..12.
 * Index: [version][ecc_index] with ecc order L, M, Q, H. */
const qrt_block_spec qrt_ecc_blocks[QRT_MAX_VERSION + 1][4] = {
    [1] = {{7, 1, 19, 0, 0}, {10, 1, 16, 0, 0}, {13, 1, 13, 0, 0}, {17, 1, 9, 0, 0}},
    [2] = {{10, 1, 34, 0, 0}, {16, 1, 28, 0, 0}, {22, 1, 22, 0, 0}, {28, 1, 16, 0, 0}},
    [3] = {{15, 1, 55, 0, 0}, {26, 1, 44, 0, 0}, {18, 2, 17, 0, 0}, {22, 2, 13, 0, 0}},
    [4] = {{20, 1, 80, 0, 0}, {18, 2, 32, 0, 0}, {26, 2, 24, 0, 0}, {16, 4, 9, 0, 0}},
    [5] = {{26, 1, 108, 0, 0}, {24, 2, 43, 0, 0}, {18, 2, 15, 2, 16}, {22, 2, 11, 2, 12}},
    [6] = {{18, 2, 68, 0, 0}, {16, 4, 27, 0, 0}, {24, 4, 19, 0, 0}, {28, 4, 15, 0, 0}},
    [7] = {{20, 2, 78, 0, 0}, {18, 4, 31, 0, 0}, {18, 2, 14, 4, 15}, {26, 4, 13, 1, 14}},
    [8] = {{24, 2, 97, 0, 0}, {22, 2, 38, 2, 39}, {22, 4, 18, 2, 19}, {26, 4, 14, 2, 15}},
    [9] = {{30, 2, 116, 0, 0}, {22, 3, 36, 2, 37}, {20, 4, 16, 4, 17}, {24, 4, 12, 4, 13}},
    [10] = {{18, 2, 68, 2, 69}, {26, 4, 43, 1, 44}, {24, 6, 19, 2, 20}, {28, 6, 15, 2, 16}},
    [11] = {{20, 4, 81, 0, 0}, {30, 1, 50, 4, 51}, {28, 4, 22, 4, 23}, {24, 3, 12, 8, 13}},
    [12] = {{24, 2, 92, 2, 93}, {22, 6, 36, 2, 37}, {26, 4, 20, 6, 21}, {28, 7, 14, 4, 15}},
};

const int qrt_alignment_centers[QRT_MAX_VERSION + 1][4] = {
    [1] = {-1, -1, -1, -1},
    [2] = {6, 18, -1, -1},
    [3] = {6, 22, -1, -1},
    [4] = {6, 26, -1, -1},
    [5] = {6, 30, -1, -1},
    [6] = {6, 34, -1, -1},
    [7] = {6, 22, 38, -1},
    [8] = {6, 24, 42, -1},
    [9] = {6, 26, 46, -1},
    [10] = {6, 28, 50, -1},
    [11] = {6, 30, 54, -1},
    [12] = {6, 32, 58, -1},
};

const int qrt_remainder_bits[QRT_MAX_VERSION + 1] = {
    [1] = 0, [2] = 7, [3] = 7, [4] = 7, [5] = 7, [6] = 7,
    [7] = 0, [8] = 0, [9] = 0, [10] = 0, [11] = 0, [12] = 0,
};

int qrt_ecc_index(char level) {
    switch (level) {
        case 'L': return 0;
        case 'M': return 1;
        case 'Q': return 2;
        case 'H': return 3;
        default: return -1;
    }
}

int qrt_ecc_format_bits(char level) {
    switch (level) {
        case 'L': return 0x1;
        case 'M': return 0x0;
        case 'Q': return 0x3;
        case 'H': return 0x2;
        default: return -1;
    }
}

int qrt_symbol_size(int version) { return 17 + 4 * version; }

int qrt_data_capacity_bits(int version, char level) {
    int e = qrt_ecc_index(level);
    if (e < 0 || version < 1 || version > QRT_MAX_VERSION) return -1;
    const qrt_block_spec *s = &qrt_ecc_blocks[version][e];
    return (s->g1_blocks * s->g1_data + s->g2_blocks * s->g2_data) * 8;
}
