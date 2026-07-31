#!/usr/bin/env bash
# schema gate helper

rec_gate() {
  local rec_json="$1"
  local base_json="$2"
  # return 0 if schema-legal vs base (keys match, mut marks respected on diffs)
  echo "$rec_json" | jq -e --argjson base "$base_json" '
    (.cols | keys) as $ck
    | ($base.cols | keys) as $bk
    | ($ck == $bk)
      and ([.cols | to_entries[] | select(.value.v != $base.cols[.key].v) | .key]
          | all(. as $k | ($base.cols[$k].mut == true) or (($base.meta.mutable // []) | index($k))))
  ' >/dev/null 2>&1
}
