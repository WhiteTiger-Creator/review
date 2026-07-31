#!/usr/bin/env bash
# decoy visitation logger

walk_help() {
  local cand_dir="$1"
  mkdir -p /app/output/probe
  local n
  n=$(find "$cand_dir" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
  printf '{"visited":%s}\n' "$n" >/app/output/probe/walk_help.json
}
