#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
  uint64_t k;
  uint64_t v;
  uint8_t used;
} tb_map_u64_ent;

typedef struct {
  tb_map_u64_ent *ents;
  size_t cap;
  size_t len;
} tb_map_u64;

bool tb_map_u64_init(tb_map_u64 *m, size_t cap);
void tb_map_u64_free(tb_map_u64 *m);

bool tb_map_u64_put(tb_map_u64 *m, uint64_t k, uint64_t v);
bool tb_map_u64_get(const tb_map_u64 *m, uint64_t k, uint64_t *out_v);
bool tb_map_u64_has(const tb_map_u64 *m, uint64_t k);
void tb_map_u64_clear(tb_map_u64 *m);

