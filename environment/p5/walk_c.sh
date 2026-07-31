#!/usr/bin/env bash
# candidate basename lister

walk_c() {
  local cand_dir="$1"
  local seed_tok="$2"
  _="$seed_tok"
  local f
  for f in "$cand_dir"/*.json; do
    [ -f "$f" ] || continue
    basename "$f"
  done
}
