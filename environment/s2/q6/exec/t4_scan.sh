#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/lib/common.sh"
# shellcheck source=/dev/null
source "$ROOT/lib/name_list.sh"

op_t4() {
  local led_path="$1"
  local mesh_path="$2"
  local out_path="$3"
  name_list /app/etc/frags >/dev/null
  {
    printf 'lane\tedition\tmark\n'
    awk 'NR>1 {print $1 "\t" $2 "\t" $3}' "$led_path"
  } > "$out_path"
  mesh_stamp_for "noop" "$mesh_path" >/dev/null || true
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  mkdir -p "$(dirname "$3")"
  op_t4 "$1" "$2" "$3"
fi
