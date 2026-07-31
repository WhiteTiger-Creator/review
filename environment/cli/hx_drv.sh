#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck disable=SC1091
source "$ROOT/s3/hx_sum.sh"
# shellcheck disable=SC1091
source "$ROOT/s3/jio_rw.sh"
# shellcheck disable=SC1091
source "$ROOT/s3/loc_util.sh"
# shellcheck disable=SC1091
source "$ROOT/m7/rec_load.sh"
# shellcheck disable=SC1091
source "$ROOT/m7/rec_gate.sh"
# shellcheck disable=SC1091
source "$ROOT/m7/mut_help.sh"
# shellcheck disable=SC1091
source "$ROOT/s3/lane_u.sh"
# shellcheck disable=SC1091
source "$ROOT/n3/wire_pack.sh"
# shellcheck disable=SC1091
source "$ROOT/n3/cost_map.sh"
# shellcheck disable=SC1091
source "$ROOT/n3/bill_help.sh"
# shellcheck disable=SC1091
source "$ROOT/s3/lane_v.sh"
# shellcheck disable=SC1091
source "$ROOT/p5/pre_gate.sh"
# shellcheck disable=SC1091
source "$ROOT/p5/score_api.sh"
# shellcheck disable=SC1091
source "$ROOT/p5/walk_help.sh"
# shellcheck disable=SC1091
source "$ROOT/p5/veil_help.sh"
# shellcheck disable=SC1091
source "$ROOT/s3/lane_w.sh"

POLICY=""
CASES=""
OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --policy) POLICY="$2"; shift 2 ;;
    --cases) CASES="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    *) shift ;;
  esac
done

if [[ -z "$POLICY" || -z "$OUT" ]]; then
  echo "usage: hx_drv.sh --policy PATH --cases DIR --out PATH" >&2
  exit 2
fi

policy_json=$(cat "$POLICY")
seed=$(echo "$policy_json" | jq -r '.seed')
budget=$(echo "$policy_json" | jq -r '.octet_budget')
flip_target=$(echo "$policy_json" | jq -r '.flip_target')
xtra_dir=$(echo "$policy_json" | jq -r '.xtra_dir')

mkdir -p /app/output/probe
: >/app/output/spend_trace.jsonl
: >/app/output/walk_side.jsonl

paths=()
if [[ -n "$CASES" && -d "$CASES" ]]; then
  while IFS= read -r -d '' f; do
    paths+=("$f")
  done < <(find "$CASES" -maxdepth 1 -name '*.json' -print0 | sort -z)
fi
if [[ -n "$xtra_dir" && -d "$xtra_dir" ]]; then
  while IFS= read -r -d '' f; do
    paths+=("$f")
  done < <(find "$xtra_dir" -maxdepth 1 -name '*.json' -print0 | sort -z)
fi

runs_json='[]'
tick_global=0

for path in "${paths[@]}"; do
  base_raw=$(rec_load "$path")
  fid=$(echo "$base_raw" | jq -r '.id')
  work=$(mktemp -d)
  cand_dir="$work/cands"
  mkdir -p "$cand_dir"

  mut_help "$base_raw" "$base_raw"
  lane_u "$base_raw" "$cand_dir" "m"

  mapfile -t order < <(lane_w_order "$cand_dir" "$seed")
  walk_help "$cand_dir"

  order_csv=$(IFS=,; echo "${order[*]}")
  walk_digest=$(hx_sum_of_str "$order_csv")
  printf '{"fixture_id":"%s","order_csv":"%s","walk_digest":"%s"}\n' \
    "$fid" "$order_csv" "$walk_digest" >>/app/output/walk_side.jsonl

  base_label=$(lane_w_score "$base_raw" "/app/environment/p5/score_api.sh")
  # also poke decoy
  _=$(veil_help "$base_raw" || true)

  picked_name=""
  picked_spend=0
  picked_label="$base_label"
  picked_rec="$base_raw"
  flip_hit=0
  t=0

  for name in "${order[@]}"; do
    [ -n "$name" ] || continue
    cand_path="$cand_dir/$name"
    [ -f "$cand_path" ] || continue
    cand_raw=$(cat "$cand_path")
    if ! rec_gate "$cand_raw" "$base_raw"; then
      t=$((t + 1))
      continue
    fi
    blob=$(wire_pack_blob "$base_raw" "$cand_raw")
    spend=$(lane_v "$blob" "$budget")
    bill_help "$spend"
    picked_flag=0
    adv_label=$(lane_w_score "$cand_raw" "/app/environment/p5/score_api.sh")
    if [[ "$spend" -le "$budget" ]] && [[ "$adv_label" == "$flip_target" ]] && [[ "$base_label" != "$flip_target" ]] && [[ "$flip_hit" -eq 0 ]]; then
      picked_flag=1
      flip_hit=1
      picked_name="$name"
      picked_spend="$spend"
      picked_label="$adv_label"
      picked_rec="$cand_raw"
    fi
    printf '{"t":%s,"fixture_id":"%s","cand_name":"%s","spend":%s,"picked":%s}\n' \
      "$t" "$fid" "$name" "$spend" "$picked_flag" >>/app/output/spend_trace.jsonl
    t=$((t + 1))
    tick_global=$((tick_global + 1))
  done

  cand_digest=$(echo "$picked_rec" | jq -c -S '.' | hx_sum_hex)
  side_hex=$(hx_sum_of_str "${fid}|${picked_spend}|${cand_digest}")

  entry=$(jq -nc \
    --arg fid "$fid" \
    --argjson flip "$flip_hit" \
    --argjson spend "$picked_spend" \
    --argjson bl "$base_label" \
    --argjson al "$picked_label" \
    --arg cd "$cand_digest" \
    --arg wd "$walk_digest" \
    --arg sh "$side_hex" \
    --argjson sd "$seed" \
    '{fixture_id:$fid,flip_hit:$flip,octet_spend:$spend,base_label:$bl,adv_label:$al,cand_digest:$cd,walk_digest:$wd,side_hex:$sh,seed:$sd}')
  runs_json=$(echo "$runs_json" | jq -c --argjson e "$entry" '. + [$e]')
  rm -rf "$work"
done

report=$(jq -nc --argjson sd "$seed" --argjson runs "$runs_json" '{seed:$sd, runs:$runs}')
mkdir -p "$(dirname "$OUT")"
printf '%s\n' "$report" >"$OUT"
