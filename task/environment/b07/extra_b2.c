#include "types.h"
#include <stddef.h>
#include <stdint.h>
#include <string.h>

extern int64_t v3_read_scale(const char *line, size_t len);

int64_t b07_pick_stamp(const char *line, size_t len) {
    const char *key = "stamp_ms=";
    size_t key_len = 9;
    for (size_t i = 0; i + key_len <= len; ++i) {
        if (strncmp(line + i, key, key_len) == 0) {
            return v3_read_scale(line + i, len - i);
        }
    }
    return 0;
}
