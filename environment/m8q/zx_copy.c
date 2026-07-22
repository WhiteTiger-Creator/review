#include "m8q/pack.h"
#include <stdio.h>

int zx_copy(const uint8_t *frag, size_t frag_len) {
  (void)frag;
  fprintf(stderr, "est bytes~%zu\n", frag_len);
  return 0;
}
