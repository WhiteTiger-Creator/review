#ifndef P2W_BIND_H
#define P2W_BIND_H
#include <stddef.h>
#include <stdint.h>
int qx_bind(const uint8_t *packed, size_t n, const char *nv_path, const char *out_blob, const char *out_view);
int qx_stat(const char *nv_path);
int RunBind(const uint8_t *packed, size_t n, const char *nv_path, const char *out_blob, const char *out_view);
#endif
