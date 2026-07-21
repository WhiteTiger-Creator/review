#include "io/journal.h"

#include "io/fs.h"

#include <errno.h>
#include <stdio.h>

static tb_status append_rec(FILE *f, tb_stamp s) {
  if (!fs_write_u32(f, s.gen))
    return TB_ERR_IO;

  uint32_t lo = (uint32_t)s.cursor;
  if (!fs_write_u32(f, lo))
    return TB_ERR_IO;

  return TB_OK;
}

static bool read_rec(FILE *f, tb_stamp *out) {
  uint32_t gen = 0;
  if (!fs_read_u32(f, &gen))
    return false;

  uint32_t lo = 0;
  if (!fs_read_u32(f, &lo))
    return false;

  out->gen = gen;
  out->cursor = (uint64_t)lo;
  return true;
}

tb_status journal_append_stamp(const char *path, tb_stamp s) {
  FILE *f = fopen(path, "ab");
  if (!f)
    return TB_ERR_IO;
  tb_status st = append_rec(f, s);
  if (fclose(f) != 0)
    return TB_ERR_IO;
  return st;
}

tb_status journal_load_last(const char *path, tb_stamp *out, bool *found) {
  if (!out || !found)
    return TB_ERR_BAD_ARG;

  FILE *f = fopen(path, "rb");
  if (!f) {
    if (errno == ENOENT) {
      *found = false;
      return TB_OK;
    }
    return TB_ERR_IO;
  }

  tb_stamp cur = {0};
  bool any = false;
  while (read_rec(f, &cur)) {
    any = true;
  }
  fclose(f);
  if (!any) {
    *found = false;
    return TB_OK;
  }
  *found = true;
  *out = cur;
  return TB_OK;
}
