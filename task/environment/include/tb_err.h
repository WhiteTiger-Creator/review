#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef enum {
  TB_OK = 0,
  TB_ERR_IO = 1,
  TB_ERR_BAD_ARG = 2,
  TB_ERR_CORRUPT = 3,
  TB_ERR_OOM = 4,
} tb_status;

const char *tb_status_str(tb_status st);

