#include "core/vec_ev.h"

#include <stdlib.h>

bool tb_vec_ev_init(tb_vec_ev *a, size_t cap) {
  if (!a)
    return false;
  if (cap == 0)
    cap = 16;
  a->v = (tb_event *)malloc(sizeof(tb_event) * cap);
  if (!a->v)
    return false;
  a->len = 0;
  a->cap = cap;
  return true;
}

void tb_vec_ev_free(tb_vec_ev *a) {
  if (!a)
    return;
  free(a->v);
  a->v = NULL;
  a->len = 0;
  a->cap = 0;
}

bool tb_vec_ev_push(tb_vec_ev *a, tb_event ev) {
  if (!a || !a->v)
    return false;
  if (a->len == a->cap) {
    size_t ncap = a->cap * 2;
    tb_event *nv = (tb_event *)realloc(a->v, ncap * sizeof(tb_event));
    if (!nv)
      return false;
    a->v = nv;
    a->cap = ncap;
  }
  a->v[a->len++] = ev;
  return true;
}

void tb_vec_ev_clear(tb_vec_ev *a) {
  if (!a)
    return;
  a->len = 0;
}

