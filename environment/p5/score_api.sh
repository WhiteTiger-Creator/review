#!/usr/bin/env bash
# frozen tabular scoring API

score_api() {
  local rec_json="$1"
  echo "$rec_json" | jq -r '
    (2.0 * .cols.f0.v)
    + (-4.0 * .cols.f1.v)
    + (1.0 * .cols.f2.v)
    + (3.0 * .cols.f3.v)
    + (-2.0)
    | if . >= 0 then 1 else 0 end
  '
}
