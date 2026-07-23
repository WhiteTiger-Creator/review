#!/usr/bin/env bash
set -euo pipefail

log() { printf '[solve] %s\n' "$1"; }

cd /app
mkdir -p /app/output
rm -f /app/output/cover_min_report.json

log "apply source fixes"
cd /solution
if grep -q 'return prune_a(stepIx, familyIx, prevFamily);' /app/m3/n4/src/bind_step.ts \
   && grep -q 'return order_c(gateFirst, side, gate)' /app/m3/k72/src/mux_g2.ts; then
  log "baseline already patched"
else
  patch -d /app -p0 --batch < oracle.patch
fi
cd /app
npm run build
/app/m3/k72/dist/fm

log "sanity-check output contract"
python3 <<'PY'
import json
from pathlib import Path

data = json.loads(Path("/app/output/cover_min_report.json").read_text(encoding="utf-8"))
assert data["summary"]["consensus_status"] == "settled"
for row in data["rows"]:
    assert row["span_rc"] and row["hop_rc"] and row["mark_rc"]
    assert row["drift_code"] == 0
PY

log "done"
