#include "cli.h"

#include <stdio.h>
#include <string.h>

static tb_status usage(void) {
  fprintf(stderr, "usage: arena --scenario <basic|stress|stress2> --profile <burst|steady> --order <a_then_b|b_then_a> --out <path> [--seed <n>]\n");
  return TB_ERR_BAD_ARG;
}

tb_order tb_order_parse(const char *s) {
  if (!s)
    return 0;
  if (strcmp(s, "a_then_b") == 0)
    return TB_ORDER_A_THEN_B;
  if (strcmp(s, "b_then_a") == 0)
    return TB_ORDER_B_THEN_A;
  return 0;
}

const char *tb_order_str(tb_order o) {
  switch (o) {
  case TB_ORDER_A_THEN_B:
    return "a_then_b";
  case TB_ORDER_B_THEN_A:
    return "b_then_a";
  default:
    return "unknown";
  }
}

tb_status tb_cli_parse(tb_cli *out, int argc, char **argv) {
  if (!out || argc <= 1)
    return usage();

  tb_cli c = {0};
  c.seed = 1;

  for (int i = 1; i < argc; i++) {
    if (strcmp(argv[i], "--scenario") == 0 && i + 1 < argc) {
      c.scenario = tb_scenario_parse(argv[++i]);
    } else if (strcmp(argv[i], "--profile") == 0 && i + 1 < argc) {
      c.profile = tb_profile_parse(argv[++i]);
    } else if (strcmp(argv[i], "--order") == 0 && i + 1 < argc) {
      c.order = tb_order_parse(argv[++i]);
    } else if (strcmp(argv[i], "--out") == 0 && i + 1 < argc) {
      c.out_path = argv[++i];
    } else if (strcmp(argv[i], "--seed") == 0 && i + 1 < argc) {
      unsigned long v = 0;
      if (sscanf(argv[++i], "%lu", &v) != 1)
        return usage();
      c.seed = (uint32_t)v;
    } else {
      return usage();
    }
  }

  if (!c.scenario || !c.profile || !c.order || !c.out_path)
    return usage();

  *out = c;
  return TB_OK;
}

