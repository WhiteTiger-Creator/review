#!/usr/bin/env bash
# defense preprocessing stage

pre_gate() {
  local rec_json="$1"
  echo "$rec_json" | jq -c '
    .cols.f1.v = (if .cols.f1.v < 0 then -.cols.f1.v else .cols.f1.v end)
    | .cols.f3.v = (
        (if .cols.f3.v < 0 then 0 else .cols.f3.v end)
        | if . > 4 then 4 else . end
      )
  '
}
