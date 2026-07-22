#include "r4x/types.h"
#include "lib/core/codec.h"
#include <stdio.h>

int hx_scan(const uint8_t *banks, size_t n) {
  /* Decoy: print header stamps only */
  if (n >= 2) fprintf(stderr, "scan tag-ish %02x%02x len=%zu\n", banks[0], banks[1], n);
  return 0;
}
