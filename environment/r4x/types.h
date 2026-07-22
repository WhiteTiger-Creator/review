#ifndef R4X_TYPES_H
#define R4X_TYPES_H
#include <stddef.h>
#include <stdint.h>
int hx_fold(const uint8_t *banks, size_t n, uint8_t *out, size_t *out_len);
int hx_scan(const uint8_t *banks, size_t n);
int RunFold(const uint8_t *banks, size_t n, uint8_t *out, size_t *out_len);
#endif
