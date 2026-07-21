#pragma once

#include "runtime/profile.h"
#include "runtime/runtime.h"
#include "runtime/script.h"
#include "tb_err.h"

#include <stdint.h>

typedef struct {
  tb_scenario scenario;
  tb_profile profile;
  tb_order order;
  const char *out_path;
  uint32_t seed;
} tb_cli;

tb_status tb_cli_parse(tb_cli *out, int argc, char **argv);

