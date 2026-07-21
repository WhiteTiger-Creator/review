#include "core/idgen.h"

void tb_idgen_init(tb_idgen *g, uint64_t seed) { g->x = seed ? seed : 0x9e3779b97f4a7c15ULL; }

uint64_t tb_idgen_next(tb_idgen *g) {
  // xorshift64*
  uint64_t x = g->x;
  x ^= x >> 12;
  x ^= x << 25;
  x ^= x >> 27;
  g->x = x;
  return x * 2685821657736338717ULL;
}

