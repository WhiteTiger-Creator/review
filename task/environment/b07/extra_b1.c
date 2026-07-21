#include "types.h"
#include <string.h>

int b07_line_has_key(const char *line, size_t len, const char *key) {
    size_t key_len = strlen(key);
    if (len < key_len) {
        return 0;
    }
    for (size_t i = 0; i + key_len <= len; ++i) {
        if (strncmp(line + i, key, key_len) == 0) {
            return 1;
        }
    }
    return 0;
}
