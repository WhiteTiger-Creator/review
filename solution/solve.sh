#!/usr/bin/env bash
set -euo pipefail

say() { printf '[marlin-oracle] %s\n' "$1"; }

say "coordinate CullY MeshT LatchH source repairs"
if grep -q 'belowEnd' /app/environment/app/v4/com/marlin/v4/CullY.java \
  && ! grep -q 'skew' /app/environment/app/w9/com/marlin/w9/MeshT.java \
  && ! grep -q 'staleFlag' /app/environment/app/x3/com/marlin/x3/LatchH.java; then
  say "frontier already repaired"
else
  cd /solution
  patch -d /app/environment -p0 --batch < patches/all-fixes.patch
fi

say "maven package marlin-engine artifact"
rm -f /app/output/gate_ledger.json
mvn -q -f /app/environment/pom.xml package

say "invoke chrono lane against enrollment packs"
java -jar /app/environment/target/marlin-engine.jar --lane chrono

say "confirm rank_rows and shift_surfaces materialize"
python3 <<'PY'
import json
from pathlib import Path
sheet = json.loads(Path("/app/output/gate_ledger.json").read_text(encoding="utf-8"))
assert "rank_rows" in sheet and "shift_surfaces" in sheet
assert sheet["rank_rows"], "missing rank_rows after chrono"
identities = {(row["pair_id"], row["side"]) for row in sheet["rank_rows"]}
assert len(identities) == len(sheet["rank_rows"])
print("marlin rows", len(sheet["rank_rows"]), "surfaces", len(sheet["shift_surfaces"]))
PY

say "site-rank chrono oracle complete"
