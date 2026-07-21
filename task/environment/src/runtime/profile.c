#include "runtime/profile.h"

#include <string.h>

tb_profile tb_profile_parse(const char *s) {
  if (!s)
    return 0;
  if (strcmp(s, "burst") == 0)
    return TB_PROFILE_BURST;
  if (strcmp(s, "steady") == 0)
    return TB_PROFILE_STEADY;
  return 0;
}

const char *tb_profile_str(tb_profile p) {
  switch (p) {
  case TB_PROFILE_BURST:
    return "burst";
  case TB_PROFILE_STEADY:
    return "steady";
  default:
    return "unknown";
  }
}

uint32_t tb_profile_should_submit(tb_profile p, uint32_t tick) {
  switch (p) {
  case TB_PROFILE_BURST:
    return tick < 10 ? 3 : (tick < 20 ? 2 : 1);
  case TB_PROFILE_STEADY:
    return (tick % 3) == 0 ? 1 : 0;
  default:
    return 0;
  }
}

