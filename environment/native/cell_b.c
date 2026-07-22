#include "cell_b.h"
#include <string.h>

uint32_t cell_b_width(void) {
    return (uint32_t)sizeof(cell_b_t);
}

size_t cell_b_tag(uint8_t *buf, size_t n) {
    const char *tag = "u4";
    size_t len = strlen(tag);
    if (len > n) {
        len = n;
    }
    memcpy(buf, tag, len);
    return len;
}
