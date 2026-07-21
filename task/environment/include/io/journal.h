#pragma once

#include "tb_err.h"

#include <stdbool.h>
#include <stdint.h>

typedef struct {
  uint32_t gen;
  uint64_t cursor;
} tb_stamp;

tb_status journal_append_stamp(const char *path, tb_stamp s);
tb_status journal_load_last(const char *path, tb_stamp *out, bool *found);

