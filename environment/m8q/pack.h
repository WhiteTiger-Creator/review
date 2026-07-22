#ifndef M8Q_PACK_H
#define M8Q_PACK_H
#include <stddef.h>
#include <stdint.h>
int zx_pack(const uint8_t *frag, size_t frag_len, const char *arms, uint8_t *out, size_t *out_len);
int zx_copy(const uint8_t *frag, size_t frag_len);
int RunPack(const uint8_t *frag, size_t frag_len, const char *arms, uint8_t *out, size_t *out_len);
#endif
