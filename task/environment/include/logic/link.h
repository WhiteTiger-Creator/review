#pragma once

#include "tb_err.h"
#include "runtime/runtime.h"

tb_status tb_link_detach(tb_rt *rt, uint32_t tick);
tb_status tb_link_attach(tb_rt *rt, uint32_t tick);

