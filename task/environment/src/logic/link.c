#include "logic/link.h"

#include "io/journal.h"

#include <string.h>

tb_status tb_link_detach(tb_rt *rt, uint32_t tick) {
  (void)tick;
  if (!rt)
    return TB_ERR_BAD_ARG;
  if (!rt->attached)
    return TB_OK;

  rt->attached = false;

  tb_stamp s = {.gen = rt->gen, .cursor = rt->cursor};
  tb_status st = journal_append_stamp(rt->journal_path, s);
  if (st != TB_OK)
    return st;

  // A "device-side" queue continues to exist while detached; the notifier doesn't.
  tb_q64_clear(&rt->notify_q);
  return TB_OK;
}

tb_status tb_link_attach(tb_rt *rt, uint32_t tick) {
  (void)tick;
  if (!rt)
    return TB_ERR_BAD_ARG;
  if (rt->attached)
    return TB_OK;

  tb_stamp last = {0};
  bool found = false;
  tb_status st = journal_load_last(rt->journal_path, &last, &found);
  if (st != TB_OK)
    return st;
  if (found) {
    rt->gen = last.gen + 1;
    rt->cursor = last.cursor;
  }

  rt->attached = true;
  return TB_OK;
}

