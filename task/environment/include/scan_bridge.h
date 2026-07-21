#pragma once
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

int forge_scan_has_key(const char *line, size_t len, const char *token);
int64_t forge_scan_record_bytes(const char *line, size_t len);

#ifdef __cplusplus
}
#endif
