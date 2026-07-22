#ifndef HX_CODEC_H
#define HX_CODEC_H
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#define HX_MAGIC 0x48585032u /* HXP2 — epoch-bearing policy blob */
#define HX_MAX_ARMS 16
#define HX_NAME_MAX 32
#define HX_DIG 32
#define HX_EPOCH_MIX 0x9E3779B97F4A7C15ull

typedef struct {
  char name[HX_NAME_MAX];
  uint8_t dig[HX_DIG];
} hx_arm;

typedef struct {
  uint32_t magic;
  uint16_t bank_tag; /* 0x00a1 deceptive, 0x0256 viable */
  uint16_t n_arms;
  hx_arm arms[HX_MAX_ARMS];
  uint32_t epoch;
  uint64_t nv_token;
} hx_blob;

int hx_hex_to_bytes(const char *hex, uint8_t *out, size_t out_len);
void hx_bytes_to_hex(const uint8_t *in, size_t n, char *out /* 2n+1 */);
int hx_load_json_bank(const char *path, uint16_t tag, uint8_t *out, size_t *out_len, size_t cap);
int hx_merge_bank_bufs(const uint8_t *a, size_t alen, const uint8_t *b, size_t blen, uint8_t *out, size_t *out_len, size_t cap);
int hx_parse_frag(const uint8_t *buf, size_t n, uint16_t *tag, hx_arm *arms, int *n_arms);
int hx_encode_blob(const hx_blob *b, uint8_t *out, size_t *out_len, size_t cap);
int hx_decode_blob(const uint8_t *in, size_t n, hx_blob *b);
uint64_t hx_nv_token_from_seed(const uint8_t *seed8);
uint64_t hx_nv_token_bound(const uint8_t *seed8, uint32_t epoch);
int hx_read_file(const char *path, uint8_t *out, size_t *out_len, size_t cap);
int hx_write_file(const char *path, const uint8_t *buf, size_t n);
void hx_sha256_hex(const uint8_t *buf, size_t n, char out64[65]);
#endif
