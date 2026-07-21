#pragma once

#include "core/ev.h"
#include "core/map_u64.h"
#include "core/queue.h"
#include "core/vec_ev.h"
#include "io/journal.h"
#include "runtime/profile.h"
#include "runtime/script.h"
#include "tb_err.h"

#include <stdbool.h>
#include <stdint.h>

typedef enum {
  TB_ORDER_A_THEN_B = 1,
  TB_ORDER_B_THEN_A = 2,
} tb_order;

tb_order tb_order_parse(const char *s);
const char *tb_order_str(tb_order o);

typedef struct {
  // "in-flight" handles are 64-bit tokens; external ids are stable u32.
  tb_map_u64 token_to_id; // token -> id
  tb_map_u64 token_done;  // canonical done-set, key depends on reconciliation

  tb_q64 in_q;
  tb_q64 done_a;
  tb_q64 done_b;
  tb_q64 notify_q;

  tb_vec_ev evlog;

  uint32_t gen;
  uint64_t cursor;
  bool attached;

  const char *journal_path;
} tb_rt;

tb_status tb_rt_init(tb_rt *rt, const char *journal_path);
void tb_rt_free(tb_rt *rt);

tb_status tb_rt_run(tb_rt *rt, tb_scenario scn, tb_profile prof, tb_order ord, uint32_t seed);

// report extraction
const tb_vec_ev *tb_rt_events(const tb_rt *rt);

