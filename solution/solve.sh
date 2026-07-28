#!/bin/bash
set -euo pipefail

# Rebuild trigger: content bump for platform re-evaluation (2026-07-27).
# Install the contingency oracle playbook, validate it, and smoke one public seat.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="/app/work/playbook"
SRC=""

for cand in \
  "${SCRIPT_DIR}/oracle-playbook/strategy.json" \
  "/solution/oracle-playbook/strategy.json" \
  "${SCRIPT_DIR}/../oracle-playbook/strategy.json"
do
  if [ -f "$cand" ]; then
    SRC="$cand"
    break
  fi
done

if [ -z "$SRC" ]; then
  echo "oracle playbook strategy.json not found near solve.sh" >&2
  exit 1
fi

mkdir -p "$TARGET"
cp -f "$SRC" "$TARGET/strategy.json"
chmod 664 "$TARGET/strategy.json" 2>/dev/null || true

export FOG_CHESS_ROOT="${FOG_CHESS_ROOT:-/opt/fog-chess-relay}"
export FOG_CHESS_OUTPUT="${FOG_CHESS_OUTPUT:-/app/output}"
mkdir -p "$FOG_CHESS_OUTPUT/generations"

"$FOG_CHESS_ROOT/bin/relaymatch" -check-playbook -bot "$TARGET"
"$FOG_CHESS_ROOT/bin/relaymatch" -match queue-pressure -bot "$TARGET" >/tmp/oracle-smoke.log 2>&1
"$FOG_CHESS_ROOT/bin/relaymatch" -match defensive-drop-fog -bot "$TARGET" >/tmp/oracle-smoke-def.log 2>&1

python3 - <<'PY'
import json
from pathlib import Path

out = Path("/app/output")
cur = (out / "current").read_text(encoding="utf-8").strip()
summary = json.loads((out / cur / "summary.json").read_text(encoding="utf-8"))
diag = json.loads((out / cur / "bot-diagnostics.json").read_text(encoding="utf-8"))
if diag.get("bot_faults", 1) != 0 or diag.get("belief_faults", 1) != 0:
    raise SystemExit(f"oracle smoke diagnostics failed: {diag}")
if not summary.get("accepted"):
    raise SystemExit(
        f"oracle smoke acceptance failed: score={summary.get('scores')} "
        f"floor={summary.get('acceptance_floor')} reason={summary.get('reason')}"
    )
print(
    f"oracle smoke ok: match={summary.get('match_id')} "
    f"score={summary['scores']['team_a']} accepted=true"
)
PY

echo "oracle playbook installed from ${SRC}"
