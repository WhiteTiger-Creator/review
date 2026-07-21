#!/bin/bash
set -euo pipefail

cat > /app/environment/b07/v3_read_scale.c <<'C'
#include "types.h"
#include <ctype.h>
#include <stdlib.h>
#include <string.h>

static const char *find_token(const char *line, size_t len, const char *key) {
    size_t key_len = strlen(key);
    for (size_t i = 0; i + key_len <= len; ++i) {
        if (strncmp(line + i, key, key_len) == 0) {
            return line + i;
        }
    }
    return NULL;
}

static int64_t read_int_after_eq(const char *line, size_t len, const char *token) {
    const char *pos = find_token(line, len, token);
    if (pos == NULL) {
        return 0;
    }
    size_t offset = (size_t)(pos - line) + strlen(token);
    while (offset < len && isspace((unsigned char)line[offset])) {
        ++offset;
    }
    char *end = NULL;
    long long value = strtoll(line + offset, &end, 10);
    if (end == line + offset) {
        return 0;
    }
    return (int64_t)value;
}

int64_t v3_read_scale(const char *line, size_t len) {
    if (line == NULL || len == 0) {
        return 0;
    }
    int64_t raw = read_int_after_eq(line, len, "size_bytes=");
    if (raw < 0) {
        return 0;
    }
    return raw;
}

int64_t b07_read_scale(const char *line, size_t len) {
    return v3_read_scale(line, len);
}
C
