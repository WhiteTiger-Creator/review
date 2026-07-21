#include "logic/nudge.h"

#include "core/ev.h"

tb_status tb_nudge_drain(tb_rt *rt, uint32_t tick) {
  (void)tick;
  if (!rt)
    return TB_ERR_BAD_ARG;

  uint64_t token = 0;
  while (tb_q64_pop(&rt->notify_q, &token)) {
    uint64_t key = (uint32_t)token;
    if (!tb_map_u64_has(&rt->token_done, key)) {
      continue;
    }
    uint64_t id64 = 0;
    if (!tb_map_u64_get(&rt->token_to_id, token, &id64))
      continue;
    tb_event ev = {.kind = TB_EV_POKE, .id = (uint32_t)id64};
    (void)tb_vec_ev_push(&rt->evlog, ev);
  }
  return TB_OK;
}
