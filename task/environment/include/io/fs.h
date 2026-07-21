#pragma once

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

bool fs_write_u32(FILE *f, uint32_t v);
bool fs_read_u32(FILE *f, uint32_t *out);

bool fs_write_u64(FILE *f, uint64_t v);
bool fs_read_u64(FILE *f, uint64_t *out);

