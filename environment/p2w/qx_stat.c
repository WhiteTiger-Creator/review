#include "p2w/bind.h"
#include <stdio.h>

int qx_stat(const char *nv_path) {
  fprintf(stderr, "nv meta path=%s\n", nv_path ? nv_path : "(null)");
  return 0;
}
