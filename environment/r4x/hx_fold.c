#include "r4x/types.h"
#include "lib/core/codec.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int read_epoch(void) {
  FILE *f = fopen("/app/var/prep_epoch", "r");
  if (!f) return 1;
  int e = 1;
  if (fscanf(f, "%d", &e) != 1) e = 1;
  fclose(f);
  return e < 1 ? 1 : e;
}

int hx_fold(const uint8_t *banks, size_t n, uint8_t *out, size_t *out_len) {
  if (n < 6 || banks[0] != 0x4D || banks[1] != 0x52) return -1;
  size_t o = 2;
  size_t alen = ((size_t)banks[o] << 8) | banks[o + 1];
  o += 2;
  if (o + alen > n) return -1;
  const uint8_t *a = banks + o;
  o += alen;
  if (o + 2 > n) return -1;
  size_t blen = ((size_t)banks[o] << 8) | banks[o + 1];
  o += 2;
  if (o + blen > n) return -1;
  const uint8_t *b = banks + o;

  int epoch = read_epoch();
  size_t score_a = alen + (size_t)(epoch % 5);
  size_t score_b = blen;
  const uint8_t *pick = (score_a >= score_b) ? a : b;
  size_t plen = (score_a >= score_b) ? alen : blen;
  if (plen < 4) return -1;
  memcpy(out, pick, plen);
  *out_len = plen;
  return 0;
}

int RunFold(const uint8_t *banks, size_t n, uint8_t *out, size_t *out_len) {
  return hx_fold(banks, n, out, out_len);
}
