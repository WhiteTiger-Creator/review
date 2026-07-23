#include <math.h>
#include "vecgen.h"

void fill_mode_vector(uint64_t seed, double *out, int n) {
    uint64_t state = seed;
    double norm2 = 0.0;
    for (int j = 0; j < n; j++) {
        state += 0x9E3779B97F4A7C15ULL;
        uint64_t z = state;
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
        z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
        z = z ^ (z >> 31);
        double unit = (double)(z >> 11) / 9007199254740992.0;
        double val = unit * 2.0 - 1.0;
        out[j] = val;
        norm2 += val * val;
    }
    if (norm2 > 0.0) {
        double inv = 1.0 / sqrt(norm2);
        for (int j = 0; j < n; j++) out[j] *= inv;
    }
}
