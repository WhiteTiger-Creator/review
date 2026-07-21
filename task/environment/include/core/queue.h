#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
  uint64_t *buf;
  size_t cap;
  size_t len;
  size_t head;
} tb_q64;

bool tb_q64_init(tb_q64 *q, size_t cap);
void tb_q64_free(tb_q64 *q);

bool tb_q64_push(tb_q64 *q, uint64_t v);
bool tb_q64_pop(tb_q64 *q, uint64_t *out);
bool tb_q64_empty(const tb_q64 *q);
void tb_q64_clear(tb_q64 *q);

