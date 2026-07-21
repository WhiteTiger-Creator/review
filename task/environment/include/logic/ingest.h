#pragma once

#include "tb_err.h"
#include "runtime/runtime.h"

tb_status tb_ingest_tick(tb_rt *rt, tb_profile prof, uint32_t tick, uint32_t *submitted_out);

