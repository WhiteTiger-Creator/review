#pragma once

#include "core/ev.h"

#include <stdbool.h>
#include <stddef.h>

typedef struct {
  tb_event *v;
  size_t len;
  size_t cap;
} tb_vec_ev;

bool tb_vec_ev_init(tb_vec_ev *a, size_t cap);
void tb_vec_ev_free(tb_vec_ev *a);
bool tb_vec_ev_push(tb_vec_ev *a, tb_event ev);
void tb_vec_ev_clear(tb_vec_ev *a);

