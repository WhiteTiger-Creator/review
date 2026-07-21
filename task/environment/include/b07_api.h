#pragma once
#ifdef __cplusplus
extern "C" {
#endif
#include <stddef.h>
#include <stdint.h>
int b07_line_has_key(const char *line, size_t len, const char *key);
int64_t b07_read_scale(const char *line, size_t len);
#ifdef __cplusplus
}
#endif
