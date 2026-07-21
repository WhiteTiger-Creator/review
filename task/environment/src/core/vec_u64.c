#include "core/vec_u64.h"

#include <stdlib.h>

bool tb_vec_u64_init(tb_vec_u64 *a, size_t cap) {
  if (!a)
    return false;
  if (cap == 0)
    cap = 8;
  a->v = (uint64_t *)malloc(sizeof(uint64_t) * cap);
  if (!a->v)
    return false;
  a->len = 0;
  a->cap = cap;
  return true;
}

void tb_vec_u64_free(tb_vec_u64 *a) {
  if (!a)
    return;
  free(a->v);
  a->v = NULL;
  a->len = 0;
  a->cap = 0;
}

bool tb_vec_u64_push(tb_vec_u64 *a, uint64_t x) {
  if (!a || !a->v)
    return false;
  if (a->len == a->cap) {
    size_t ncap = a->cap * 2;
    uint64_t *nv = (uint64_t *)realloc(a->v, ncap * sizeof(uint64_t));
    if (!nv)
      return false;
    a->v = nv;
    a->cap = ncap;
  }
  a->v[a->len++] = x;
  return true;
}

void tb_vec_u64_clear(tb_vec_u64 *a) {
  if (!a)
    return;
  a->len = 0;
}

