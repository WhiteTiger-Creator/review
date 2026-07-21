#pragma once

#include <stdint.h>

typedef enum {
  TB_EV_SUBMIT = 1,
  TB_EV_DONE = 2,
  TB_EV_POKE = 3,
} tb_ev_kind;

typedef struct {
  tb_ev_kind kind;
  uint32_t id;
} tb_event;

