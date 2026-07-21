#include "runtime/script.h"

#include <string.h>

tb_scenario tb_scenario_parse(const char *s) {
  if (!s)
    return 0;
  if (strcmp(s, "basic") == 0)
    return TB_SCN_BASIC;
  if (strcmp(s, "stress") == 0)
    return TB_SCN_STRESS;
  if (strcmp(s, "stress2") == 0)
    return TB_SCN_STRESS2;
  return 0;
}

const char *tb_scenario_str(tb_scenario scn) {
  switch (scn) {
  case TB_SCN_BASIC:
    return "basic";
  case TB_SCN_STRESS:
    return "stress";
  case TB_SCN_STRESS2:
    return "stress2";
  default:
    return "unknown";
  }
}

bool tb_script_for(tb_scenario scn, tb_script *out) {
  if (!out)
    return false;
  tb_script s = {0};
  switch (scn) {
  case TB_SCN_BASIC:
    s.ticks = 40;
    s.detach_at = 0;
    s.detach_len = 0;
    s.detach2_at = 0;
    s.detach2_len = 0;
    break;
  case TB_SCN_STRESS:
    s.ticks = 80;
    s.detach_at = 22;
    s.detach_len = 10;
    s.detach2_at = 0;
    s.detach2_len = 0;
    break;
  case TB_SCN_STRESS2:
    s.ticks = 110;
    s.detach_at = 26;
    s.detach_len = 10;
    s.detach2_at = 68;
    s.detach2_len = 12;
    break;
  default:
    return false;
  }
  *out = s;
  return true;
}

