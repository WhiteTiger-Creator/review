#include "tb_err.h"

const char *tb_status_str(tb_status st) {
  switch (st) {
  case TB_OK:
    return "ok";
  case TB_ERR_IO:
    return "io";
  case TB_ERR_BAD_ARG:
    return "bad_arg";
  case TB_ERR_CORRUPT:
    return "corrupt";
  case TB_ERR_OOM:
    return "oom";
  default:
    return "unknown";
  }
}

