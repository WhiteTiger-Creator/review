#include "logic/settle.h"

#include "runtime/runtime.h"

// Deterministic "work takes time": only move certain tokens each tick.
static bool ready(uint64_t token, uint32_t tick) {
  // spread completion across ticks, but deterministic and input-dependent
  return (((uint32_t)token) ^ tick) % 3 == 0;
}

static bool lane_a(uint64_t token, uint32_t tick) {
  // Choose which completion source produced the "done" record.
  return ((((uint32_t)(token >> 32)) + (uint32_t)token + tick) & 1u) == 0u;
}

tb_status tb_settle_tick(tb_rt *rt, uint32_t tick) {
  if (!rt)
    return TB_ERR_BAD_ARG;

  // rotate through at most a bounded number so runs are stable
  size_t spins = rt->in_q.len;
  for (size_t i = 0; i < spins; i++) {
    uint64_t token = 0;
    if (!tb_q64_pop(&rt->in_q, &token))
      break;

    if (ready(token, tick)) {
      if (lane_a(token, tick)) {
        if (!tb_q64_push(&rt->done_a, token))
          return TB_ERR_CORRUPT;
      } else {
        if (!tb_q64_push(&rt->done_b, token))
          return TB_ERR_CORRUPT;
      }
      if (rt->attached) {
        // The notifier is only live while attached.
        if (!tb_q64_push(&rt->notify_q, token))
          return TB_ERR_CORRUPT;
      }
    } else {
      // not ready, requeue at tail
      if (!tb_q64_push(&rt->in_q, token))
        return TB_ERR_CORRUPT;
    }
  }

  return TB_OK;
}

