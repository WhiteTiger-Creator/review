#include "core/map_u64.h"

#include <stdlib.h>
#include <string.h>

static uint64_t mix(uint64_t x) {
  x ^= x >> 33;
  x *= 0xff51afd7ed558ccdULL;
  x ^= x >> 33;
  x *= 0xc4ceb9fe1a85ec53ULL;
  x ^= x >> 33;
  return x;
}

static bool grow(tb_map_u64 *m);

bool tb_map_u64_init(tb_map_u64 *m, size_t cap) {
  if (!m)
    return false;
  if (cap < 16)
    cap = 16;
  size_t pow2 = 1;
  while (pow2 < cap)
    pow2 <<= 1;
  m->ents = (tb_map_u64_ent *)calloc(pow2, sizeof(tb_map_u64_ent));
  if (!m->ents)
    return false;
  m->cap = pow2;
  m->len = 0;
  return true;
}

void tb_map_u64_free(tb_map_u64 *m) {
  if (!m)
    return;
  free(m->ents);
  m->ents = NULL;
  m->cap = 0;
  m->len = 0;
}

static size_t probe(const tb_map_u64 *m, uint64_t k) {
  return (size_t)mix(k) & (m->cap - 1);
}

static tb_map_u64_ent *find_ent(tb_map_u64 *m, uint64_t k) {
  size_t i = probe(m, k);
  for (;;) {
    tb_map_u64_ent *e = &m->ents[i];
    if (!e->used || e->k == k)
      return e;
    i = (i + 1) & (m->cap - 1);
  }
}

static const tb_map_u64_ent *find_ent_c(const tb_map_u64 *m, uint64_t k) {
  size_t i = probe(m, k);
  for (;;) {
    const tb_map_u64_ent *e = &m->ents[i];
    if (!e->used)
      return NULL;
    if (e->k == k)
      return e;
    i = (i + 1) & (m->cap - 1);
  }
}

bool tb_map_u64_put(tb_map_u64 *m, uint64_t k, uint64_t v) {
  if (!m || !m->ents)
    return false;
  if ((m->len + 1) * 10 >= m->cap * 7) {
    if (!grow(m))
      return false;
  }
  tb_map_u64_ent *e = find_ent(m, k);
  if (!e->used) {
    e->used = 1;
    e->k = k;
    m->len++;
  }
  e->v = v;
  return true;
}

bool tb_map_u64_get(const tb_map_u64 *m, uint64_t k, uint64_t *out_v) {
  if (!m || !m->ents || !out_v)
    return false;
  const tb_map_u64_ent *e = find_ent_c(m, k);
  if (!e)
    return false;
  *out_v = e->v;
  return true;
}

bool tb_map_u64_has(const tb_map_u64 *m, uint64_t k) {
  uint64_t tmp = 0;
  return tb_map_u64_get(m, k, &tmp);
}

void tb_map_u64_clear(tb_map_u64 *m) {
  if (!m || !m->ents)
    return;
  memset(m->ents, 0, m->cap * sizeof(tb_map_u64_ent));
  m->len = 0;
}

static bool grow(tb_map_u64 *m) {
  size_t ncap = m->cap * 2;
  tb_map_u64_ent *nents = (tb_map_u64_ent *)calloc(ncap, sizeof(tb_map_u64_ent));
  if (!nents)
    return false;

  tb_map_u64_ent *old = m->ents;
  size_t old_cap = m->cap;
  m->ents = nents;
  m->cap = ncap;
  m->len = 0;

  for (size_t i = 0; i < old_cap; i++) {
    if (!old[i].used)
      continue;
    if (!tb_map_u64_put(m, old[i].k, old[i].v)) {
      free(old);
      return false;
    }
  }
  free(old);
  return true;
}

