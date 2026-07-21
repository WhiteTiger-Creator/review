#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
  uint64_t *v;
  size_t len;
  size_t cap;
} tb_vec_u64;

bool tb_vec_u64_init(tb_vec_u64 *a, size_t cap);
void tb_vec_u64_free(tb_vec_u64 *a);
bool tb_vec_u64_push(tb_vec_u64 *a, uint64_t x);
void tb_vec_u64_clear(tb_vec_u64 *a);

