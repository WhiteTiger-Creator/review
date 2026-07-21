#include "core/queue.h"

#include <stdlib.h>
#include <string.h>

bool tb_q64_init(tb_q64 *q, size_t cap) {
  if (!q || cap == 0)
    return false;
  q->buf = (uint64_t *)calloc(cap, sizeof(uint64_t));
  if (!q->buf)
    return false;
  q->cap = cap;
  q->len = 0;
  q->head = 0;
  return true;
}

void tb_q64_free(tb_q64 *q) {
  if (!q)
    return;
  free(q->buf);
  q->buf = NULL;
  q->cap = 0;
  q->len = 0;
  q->head = 0;
}

static size_t idx(const tb_q64 *q, size_t i) { return (q->head + i) % q->cap; }

bool tb_q64_push(tb_q64 *q, uint64_t v) {
  if (!q || !q->buf)
    return false;
  if (q->len == q->cap)
    return false;
  q->buf[idx(q, q->len)] = v;
  q->len++;
  return true;
}

bool tb_q64_pop(tb_q64 *q, uint64_t *out) {
  if (!q || !q->buf || !out)
    return false;
  if (q->len == 0)
    return false;
  *out = q->buf[q->head];
  q->head = (q->head + 1) % q->cap;
  q->len--;
  return true;
}

bool tb_q64_empty(const tb_q64 *q) { return !q || q->len == 0; }

void tb_q64_clear(tb_q64 *q) {
  if (!q || !q->buf)
    return;
  q->len = 0;
  q->head = 0;
  memset(q->buf, 0, q->cap * sizeof(uint64_t));
}

