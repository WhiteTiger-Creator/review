#!/usr/bin/env bash
set -euo pipefail
ROOT="/app/environment/pack/seed"
LEDGER="/app/environment/pack/ledger/waves.ndjson"
CLEAN="/app/environment/pack/checkpoints/waves_clean.ndjson"
if [[ "${1:-}" == "--preserve-anchor" ]]; then
  cp "${ROOT}/token_seed.bin" "${ROOT}/.anchor_staging"
  echo -n 0 > "${ROOT}/.roll_scratch"
  echo -n 0 > "${ROOT}/.storm_gen"
  cp "${CLEAN}" "${LEDGER}"
  exit 0
fi
count=0
if [[ -f "${ROOT}/.roll_scratch" ]]; then
  count="$(tr -d ' \n' < "${ROOT}/.roll_scratch" || echo 0)"
fi
echo $((count + 1)) > "${ROOT}/.roll_scratch"
rm -f "${ROOT}/.anchor_staging"
echo -n 3 > "${ROOT}/.storm_gen"
# Tombstone the latest live wave so tip and policy selection go incoherent until preserve.
python3 - <<'PY'
import json
from pathlib import Path
path = Path("/app/environment/pack/ledger/waves.ndjson")
rows = []
for line in path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    rows.append(json.loads(line))
live = [i for i, r in enumerate(rows) if not r.get("tomb")]
if live:
    rows[live[-1]]["tomb"] = True
# Ensure a higher-gen decoy is live after scrub so a naive tip reader drifts.
found = False
for r in rows:
    if r.get("gen") == 1:
        r["tomb"] = False
        found = True
if not found:
    rows.append({"gen": 1, "family": "decoy", "unit": "sd", "tomb": False})
path.write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n", encoding="utf-8")
PY
