#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source /app/s2/q6/lib/common.sh
# shellcheck source=/dev/null
source "$ROOT/lib/json_emit.sh"
# shellcheck source=/dev/null
source "$ROOT/lib/tree_pretty.sh"

phase_k9() {
  local table_path="$1"
  local gen_path="$2"
  local mesh_path="$3"
  local out_json="$4"
  tree_pretty "$mesh_path" >/dev/null
  printf '{' > "$out_json"
  local args=()
  while IFS=$'\t' read -r lane edition layer; do
    [ -z "$lane" ] && continue
    [ "$lane" = "lane" ] && continue
    local pick stamp dig
    pick="$(awk -v p="$lane" 'NR>1 && $1==p && $3=="live" {print $2; exit}' /app/data/led_rows.tsv)"
    if [ -z "$pick" ]; then
      pick="$edition"
    fi
    stamp="$(mesh_stamp_for "$pick" "$mesh_path")"
    dig="$(digest16 "$lane" "$pick" "$stamp")"
    args+=("$lane" "$stamp" "$dig" "$pick")
  done < "$table_path"
  emit_rows_json "$out_json" "${args[@]}"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  phase_k9 "$1" "$2" "$3" "$4"
fi
