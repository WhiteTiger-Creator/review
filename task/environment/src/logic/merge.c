#include "logic/merge.h"

#include "core/ev.h"

static bool drain_one(tb_rt *rt, tb_q64 *q, uint32_t tick) {
  (void)tick;
  uint64_t token = 0;
  if (!tb_q64_pop(q, &token))
    return false;

  uint64_t key = (uint32_t)token;

  if (!tb_map_u64_has(&rt->token_done, key)) {
    uint64_t id64 = 0;
    if (!tb_map_u64_get(&rt->token_to_id, token, &id64)) {
      return true;
    }
    (void)tb_map_u64_put(&rt->token_done, key, 1);
    tb_event ev = {.kind = TB_EV_DONE, .id = (uint32_t)id64};
    (void)tb_vec_ev_push(&rt->evlog, ev);
  }
  return true;
}

tb_status tb_merge_drain(tb_rt *rt, uint32_t tick, tb_order ord) {
  if (!rt)
    return TB_ERR_BAD_ARG;

  tb_q64 *a = &rt->done_a;
  tb_q64 *b = &rt->done_b;

  if (ord == TB_ORDER_A_THEN_B) {
    while (drain_one(rt, a, tick)) {
    }
    while (drain_one(rt, b, tick)) {
    }
  } else {
    while (drain_one(rt, b, tick)) {
    }
    while (drain_one(rt, a, tick)) {
    }
  }

  return TB_OK;
}
