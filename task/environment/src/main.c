#include "cli.h"
#include "report.h"
#include "runtime/runtime.h"
#include "tb_err.h"

#include <stdio.h>

int main(int argc, char **argv) {
  tb_cli cli = {0};
  tb_status st = tb_cli_parse(&cli, argc, argv);
  if (st != TB_OK) {
    fprintf(stderr, "cli: %s\n", tb_status_str(st));
    return 2;
  }

  // Per-invocation: persistence is only meant to model detach/reattach inside a run.
  (void)remove("/app/run/state.bin");

  tb_rt rt = {0};
  st = tb_rt_init(&rt, "/app/run/state.bin");
  if (st != TB_OK) {
    fprintf(stderr, "init: %s\n", tb_status_str(st));
    return 2;
  }

  st = tb_rt_run(&rt, cli.scenario, cli.profile, cli.order, cli.seed);
  if (st != TB_OK) {
    fprintf(stderr, "run: %s\n", tb_status_str(st));
    tb_rt_free(&rt);
    return 1;
  }

  int rc = tb_report_write_json(cli.out_path, cli.scenario, cli.profile, tb_rt_events(&rt));
  tb_rt_free(&rt);
  return rc;
}

