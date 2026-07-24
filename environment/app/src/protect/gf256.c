#include "qr_composer.h"

/* GF(256) arithmetic with primitive polynomial 0x11D and Reed-Solomon
 * generator/remainder helpers. */

static uint8_t gf_exp_tab[512];
static uint8_t gf_log_tab[256];
static int gf_ready = 0;

void qrt_gf_init(void) {
    if (gf_ready) return;
    int x = 1;
    for (int i = 0; i < 255; i++) {
        gf_exp_tab[i] = (uint8_t)x;
        gf_log_tab[x] = (uint8_t)i;
        x <<= 1;
        if (x & 0x100) x ^= 0x11D;
    }
    for (int i = 255; i < 512; i++) gf_exp_tab[i] = gf_exp_tab[i - 255];
    gf_ready = 1;
}

uint8_t qrt_gf_exp(int i) {
    qrt_gf_init();
    return gf_exp_tab[i % 255];
}

uint8_t qrt_gf_mul(uint8_t a, uint8_t b) {
    if (a == 0 || b == 0) return 0;
    qrt_gf_init();
    return gf_exp_tab[gf_log_tab[a] + gf_log_tab[b]];
}

/* Build RS generator polynomial of the requested degree.
 * Output is MSB-first with out[0] == 1, length degree + 1. */
void qrt_rs_generator(int degree, uint8_t *out) {
    qrt_gf_init();
    uint8_t gen[QRT_MAX_BLOCKS * 32 + 1];
    int len = 1;
    gen[0] = 1; /* little-endian coefficient of x^0 */
    for (int k = 1; k <= degree; k++) {
        uint8_t nxt[QRT_MAX_BLOCKS * 32 + 1];
        for (int i = 0; i <= len; i++) nxt[i] = 0;
        for (int i = 0; i < len; i++) {
            nxt[i] ^= qrt_gf_mul(gen[i], qrt_gf_exp(k));
            nxt[i + 1] ^= gen[i];
        }
        len++;
        for (int i = 0; i < len; i++) gen[i] = nxt[i];
    }
    for (int i = 0; i <= degree; i++) out[i] = gen[degree - i];
}

void qrt_rs_remainder(const uint8_t *data, int len, int degree, uint8_t *out) {
    uint8_t gen[QRT_MAX_BLOCKS * 32 + 1];
    qrt_rs_generator(degree, gen);
    uint8_t rem[QRT_MAX_BLOCKS * 32];
    for (int i = 0; i < degree; i++) rem[i] = 0;
    for (int i = 0; i < len; i++) {
        uint8_t factor = data[i] ^ rem[0];
        for (int j = 0; j < degree - 1; j++) rem[j] = rem[j + 1];
        rem[degree - 1] = 0;
        if (factor) {
            for (int j = 0; j < degree; j++) rem[j] ^= qrt_gf_mul(gen[j + 1], factor);
        }
    }
    for (int i = 0; i < degree; i++) out[i] = rem[i];
}
