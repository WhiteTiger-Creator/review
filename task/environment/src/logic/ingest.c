#include "logic/ingest.h"

#include "core/ev.h"
#include "runtime/profile.h"

static uint64_t make_token(uint32_t gen, uint64_t cursor) { return (((uint64_t)gen) << 32) ^ cursor; }

tb_status tb_ingest_tick(tb_rt *rt, tb_profile prof, uint32_t tick, uint32_t *submitted_out) {
  if (!rt || !submitted_out)
    return TB_ERR_BAD_ARG;

  uint32_t n = tb_profile_should_submit(prof, tick);
  *submitted_out = n;

  for (uint32_t i = 0; i < n; i++) {
    uint32_t id = (uint32_t)(rt->cursor & 0xffffffffu);
    uint64_t token = make_token(rt->gen, rt->cursor);
    rt->cursor++;

    if (!tb_map_u64_put(&rt->token_to_id, token, (uint64_t)id))
      return TB_ERR_OOM;
    if (!tb_q64_push(&rt->in_q, token))
      return TB_ERR_CORRUPT;

    tb_event ev = {.kind = TB_EV_SUBMIT, .id = id};
    if (!tb_vec_ev_push(&rt->evlog, ev))
      return TB_ERR_OOM;
  }

  return TB_OK;
}

