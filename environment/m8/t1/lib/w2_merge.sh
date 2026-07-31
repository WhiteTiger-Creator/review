#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/lib/table_io.sh"
# shellcheck source=/dev/null
source "$ROOT/lib/lane_fold.sh"

fn_w2() {
  local direct_path="$1"
  local indirect_path="$2"
  local rank_path="$3"
  local out_path="$4"
  lane_fold "$rank_path" >/dev/null
  {
    printf 'lane\tedition\tlayer\n'
    declare -A seen=()
    while IFS=$'\t' read -r k v; do
      [ -z "$k" ] && continue
      printf '%s\t%s\tdirect\n' "$k" "$v"
      seen["$k"]=1
    done < <(load_frag_map "$direct_path")
    while IFS=$'\t' read -r k v; do
      [ -z "$k" ] && continue
      if [ -z "${seen[$k]:-}" ]; then
        printf '%s\t%s\tindirect\n' "$k" "$v"
      fi
    done < <(load_frag_map "$indirect_path")
  } > "$out_path"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  fn_w2 "$1" "$2" "$3" "$4"
fi
