#include "types.h"
#include <stddef.h>

unsigned long j2_fold_line(unsigned long seed, const char *line, size_t len) {
    unsigned long h = seed;
    for (size_t i = 0; i < len; ++i) {
        h ^= (unsigned char)line[i];
        h *= 1099511628211UL;
    }
    return h;
}
