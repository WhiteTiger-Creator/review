#!/usr/bin/env bash
# TLV/wire packer (size accounting only)

wire_pack_size() {
  local base_json="$1"
  local cand_json="$2"
  jq -n --argjson base "$base_json" --argjson cand "$cand_json" '
    [$base.cols | to_entries[] as $e
      | select($e.value.v != $cand.cols[$e.key].v)
      | (2 + ($e.value.w | tonumber))]
    | add // 0
  '
}

wire_pack_blob() {
  local base_json="$1"
  local cand_json="$2"
  jq -nc --argjson base "$base_json" --argjson cand "$cand_json" \
    '{base:$base, cand:$cand}'
}
