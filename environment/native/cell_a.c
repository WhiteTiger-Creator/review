#include "cell_a.h"
#include <string.h>

uint32_t cell_a_width(void) {
    return (uint32_t)sizeof(cell_a_t);
}

uint32_t cell_a_align(void) {
    return (uint32_t)_Alignof(cell_a_t);
}

size_t cell_a_tag(uint8_t *buf, size_t n) {
    const char *tag;
#if TAG_MODE == 2
    tag = "t4w";
#else
    tag = "t4";
#endif
    size_t len = strlen(tag);
    if (len > n) {
        len = n;
    }
    memcpy(buf, tag, len);
    return len;
}
