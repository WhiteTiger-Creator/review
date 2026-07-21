#pragma once

#include "core/vec_ev.h"
#include "runtime/profile.h"
#include "runtime/script.h"

#include <stdint.h>

// Writes report.json as described in instruction.md.
int tb_report_write_json(const char *path, tb_scenario scn, tb_profile prof, const tb_vec_ev *evs);

