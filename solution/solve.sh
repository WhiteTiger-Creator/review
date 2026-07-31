#!/bin/bash
set -euo pipefail

cat > /app/s2/q6/exec/t4_scan.sh <<'EOF'
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
  local gen_path="/app/data/gen_sheet.dat"
  {
    printf 'lane\tedition\tmark\n'
    while IFS=$'\t' read -r lane edition mark; do
      [ -z "$lane" ] && continue
      [ "$lane" = "lane" ] && continue
      local live_ed stamp
      live_ed="$(awk -F'|' -v p="$lane" '$1==p {print $2; exit}' "$gen_path")"
      stamp="$(mesh_stamp_for "$edition" "$mesh_path")"
      if [ -n "$live_ed" ] && [ "$edition" = "$live_ed" ] && [ -n "$stamp" ]; then
        printf '%s\t%s\tlive\n' "$lane" "$edition"
      else
        printf '%s\t%s\ttomb\n' "$lane" "$edition"
      fi
    done < "$led_path"
  } > "$out_path"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  mkdir -p "$(dirname "$3")"
  op_t4 "$1" "$2" "$3"
fi
EOF
chmod +x /app/s2/q6/exec/t4_scan.sh

cat > /app/m8/t1/lib/w2_merge.sh <<'EOF'
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
  local w_direct w_indirect
  w_direct="$(read_rank_weight direct "$rank_path")"
  w_indirect="$(read_rank_weight indirect "$rank_path")"
  declare -A ed_for=()
  declare -A layer_for=()
  declare -A weight_for=()
  while IFS=$'\t' read -r k v; do
    [ -z "$k" ] && continue
    ed_for["$k"]="$v"
    layer_for["$k"]="direct"
    weight_for["$k"]="$w_direct"
  done < <(load_frag_map "$direct_path")
  while IFS=$'\t' read -r k v; do
    [ -z "$k" ] && continue
    local cur="${weight_for[$k]:-0}"
    if [ -z "${ed_for[$k]:-}" ] || [ "$w_indirect" -gt "$cur" ]; then
      ed_for["$k"]="$v"
      layer_for["$k"]="indirect"
      weight_for["$k"]="$w_indirect"
    fi
  done < <(load_frag_map "$indirect_path")
  {
    printf 'lane\tedition\tlayer\n'
    for k in "${!ed_for[@]}"; do
      printf '%s\t%s\t%s\n' "$k" "${ed_for[$k]}" "${layer_for[$k]}"
    done | sort
  } > "$out_path"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  fn_w2 "$1" "$2" "$3" "$4"
fi
EOF
chmod +x /app/m8/t1/lib/w2_merge.sh

cat > /app/v3/d4/lib/k9_phase.sh <<'EOF'
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
  local tmp
  tmp="$(mktemp)"
  local args=()
  while IFS=$'\t' read -r lane edition layer; do
    [ -z "$lane" ] && continue
    [ "$lane" = "lane" ] && continue
    local pick stamp dig
    pick="$(awk -F'|' -v p="$lane" '$1==p {print $2; exit}' "$gen_path")"
    if [ -z "$pick" ]; then
      pick="$edition"
    fi
    stamp="$(mesh_stamp_for "$pick" "$mesh_path")"
    dig="$(digest16 "$lane" "$pick" "$stamp")"
    args+=("$lane" "$stamp" "$dig" "$pick")
  done < "$table_path"
  emit_rows_json "$tmp" "${args[@]}"
  mv -f "$tmp" "$out_json"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  phase_k9 "$1" "$2" "$3" "$4"
fi
EOF
chmod +x /app/v3/d4/lib/k9_phase.sh

bash /app/scripts/run_batch.sh

python3 <<'PY'
import hashlib
import json
from pathlib import Path

report = json.loads(Path("/app/output/inventory_report.json").read_text(encoding="utf-8"))
rows = {r["lane_id"]: r for r in report["rows"]}
assert set(rows) == {"c2", "r7"}
assert rows["c2"]["selected_edition"] == "px-a17-new"
assert rows["r7"]["selected_edition"] == "qx-b22-b"
for lane, row in rows.items():
    expected = hashlib.sha256(
        f'{lane}|{row["selected_edition"]}|{row["edition_stamp"]}'.encode()
    ).hexdigest()[:16]
    assert row["inventory_digest"] == expected
scan = Path("/app/output/inv_scan.tsv").read_text(encoding="utf-8")
assert "tomb" in scan
merged = Path("/app/output/merged.tsv").read_text(encoding="utf-8")
assert "indirect" in merged
PY
