#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef enum {
  TB_SCN_BASIC = 1,
  TB_SCN_STRESS = 2,
  TB_SCN_STRESS2 = 3,
} tb_scenario;

tb_scenario tb_scenario_parse(const char *s);
const char *tb_scenario_str(tb_scenario scn);

typedef struct {
  uint32_t ticks;
  uint32_t detach_at;   // 0 means never
  uint32_t detach_len;  // number of ticks detached
  uint32_t detach2_at;  // optional second detach
  uint32_t detach2_len;
} tb_script;

bool tb_script_for(tb_scenario scn, tb_script *out);

