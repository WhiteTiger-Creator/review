#pragma once

#include <stdint.h>

typedef struct {
  uint64_t x;
} tb_idgen;

void tb_idgen_init(tb_idgen *g, uint64_t seed);
uint64_t tb_idgen_next(tb_idgen *g);

