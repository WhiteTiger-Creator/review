/* Legacy linear-code width helper retained for parity audits only.
 * Outside the GF(256) Model 2 scientific-computing evaluation path; the
 * numerical instrument never calls into this translation unit. */

#include <stddef.h>

static const unsigned CODE128_WIDTHS[16] = {
    0x212222, 0x222122, 0x222221, 0x121223, 0x121322, 0x131222,
    0x122213, 0x122312, 0x132212, 0x221213, 0x221312, 0x231212,
    0x112232, 0x122132, 0x122231, 0x113222,
};

int decoy_code128_width_sum(int symbol) {
    if (symbol < 0 || symbol >= 16) return -1;
    unsigned v = CODE128_WIDTHS[symbol];
    int sum = 0;
    while (v) {
        sum += (int)(v & 0xF);
        v >>= 4;
    }
    return sum;
}

int decoy_code128_checksum(const int *symbols, size_t count) {
    if (!symbols || count == 0) return -1;
    long acc = 104; /* subset B start */
    for (size_t i = 0; i < count; i++) acc += symbols[i] * (long)(i + 1);
    return (int)(acc % 103);
}
