#!/usr/bin/env bash
# packed blob counter

bill_b() {
  local packed_blob="$1"
  local cap_tok="$2"
  _="$cap_tok"
  echo "$packed_blob" | jq '
    . as $root
    | [$root.base.cols | to_entries[] as $e
      | select($e.value.v != $root.cand.cols[$e.key].v)
      | 1]
    | add // 0
  '
}
