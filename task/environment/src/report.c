#include "report.h"

#include <stdio.h>

static const char *kind_str(tb_ev_kind k) {
  switch (k) {
  case TB_EV_SUBMIT:
    return "submit";
  case TB_EV_DONE:
    return "complete";
  case TB_EV_POKE:
    return "notify";
  default:
    return "unknown";
  }
}

int tb_report_write_json(const char *path, tb_scenario scn, tb_profile prof, const tb_vec_ev *evs) {
  FILE *f = fopen(path, "wb");
  if (!f)
    return 1;

  fprintf(f, "{\n");
  fprintf(f, "  \"scenario\": \"%s\",\n", tb_scenario_str(scn));
  fprintf(f, "  \"profile\": \"%s\",\n", tb_profile_str(prof));
  fprintf(f, "  \"events\": [\n");
  for (size_t i = 0; i < evs->len; i++) {
    const tb_event *ev = &evs->v[i];
    fprintf(f, "    {\"kind\": \"%s\", \"id\": %u}%s\n", kind_str(ev->kind), ev->id,
            (i + 1 == evs->len) ? "" : ",");
  }
  fprintf(f, "  ]\n");
  fprintf(f, "}\n");
  fclose(f);
  return 0;
}

