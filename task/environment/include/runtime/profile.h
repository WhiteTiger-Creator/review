#pragma once

#include <stdint.h>

typedef enum {
  TB_PROFILE_BURST = 1,
  TB_PROFILE_STEADY = 2,
} tb_profile;

tb_profile tb_profile_parse(const char *s);
const char *tb_profile_str(tb_profile p);

// Deterministic submission cadence.
uint32_t tb_profile_should_submit(tb_profile p, uint32_t tick);

