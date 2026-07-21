#include "types.h"
#include <stdlib.h>

int64_t m14_shadow_carry(int64_t base, int64_t carry) {
    if (carry < 0) {
        return base;
    }
    return base + carry / 2;
}
