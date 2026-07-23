#!/usr/bin/env bash
set -euo pipefail
CASE="${1:?case id required}"
STATE_ROOT="${LANE_STATE_ROOT:-/tmp/lane_state}"
OUT_PATH="${LANE_OUT:-/app/output/training_observations.json}"
CASES="/app/environment/data/matrix_cases.json"
CONFIG="/app/environment/configs/train.toml"
PACK="/app/environment/data/pack_rows.json"
mkdir -p "$(dirname "$OUT_PATH")"
rm -f "$OUT_PATH"

# Fresh state unless caller opts into resume-only.
if [ "${LANE_KEEP_STATE:-0}" != "1" ]; then
  rm -rf "$STATE_ROOT"
  mkdir -p "$STATE_ROOT"
fi

read_case() {
  python3 - <<PY
import json, sys
cases = json.load(open("$CASES"))["cases"]
spec = next((c for c in cases if c["id"] == "$CASE"), None)
if not spec:
    sys.exit(2)
print(json.dumps(spec))
PY
}

SPEC="$(read_case)"
MODE="$(python3 - <<PY
import json
print(json.loads('''$SPEC''')["mode"])
PY
)"
SEGMENTED="$(python3 - <<PY
import json
print("yes" if json.loads('''$SPEC''').get("segmented") else "no")
PY
)"

if [ "$MODE" = "migrate_load" ] && [ "$SEGMENTED" = "no" ]; then
  exec /app/bin/lanectl migrate \
    --scenario "$CASE" \
    --config "$CONFIG" \
    --pack "$PACK" \
    --state "$STATE_ROOT" \
    --out "$OUT_PATH"
fi

if [ "$MODE" = "assess_migrate" ]; then
  /app/bin/lanectl migrate \
    --scenario "$CASE" \
    --config "$CONFIG" \
    --pack "$PACK" \
    --state "$STATE_ROOT" \
    --out "$OUT_PATH"
  exec /app/bin/lanectl assess \
    --config "$CONFIG" \
    --pack "$PACK" \
    --state "$STATE_ROOT" \
    --out "$OUT_PATH"
fi

if [ "$SEGMENTED" = "yes" ]; then
  HALT_AT="$(python3 - <<PY
import json
print(json.loads('''$SPEC''')["halt_at"])
PY
)"
  /app/bin/lanectl train \
    --scenario "$CASE" \
    --mode "$MODE" \
    --config "$CONFIG" \
    --pack "$PACK" \
    --state "$STATE_ROOT" \
    --out "$OUT_PATH" \
    --halt-at "$HALT_AT"
  exec /app/bin/lanectl resume \
    --config "$CONFIG" \
    --pack "$PACK" \
    --state "$STATE_ROOT" \
    --out "$OUT_PATH"
fi

exec /app/bin/lanectl train \
  --scenario "$CASE" \
  --mode "$MODE" \
  --config "$CONFIG" \
  --pack "$PACK" \
  --state "$STATE_ROOT" \
  --out "$OUT_PATH"
