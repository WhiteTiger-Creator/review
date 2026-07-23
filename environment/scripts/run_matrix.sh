#!/usr/bin/env bash
# Run the full documented matrix and write /app/output/matrix_report.json
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="${NEXUS_OUT:-/app/output}"
mkdir -p "$OUT"
MATRIX="$ROOT/contracts/matrix_arms.json"

python3 - <<'PY' "$MATRIX" "$OUT" "$ROOT"
import json, os, subprocess, sys
matrix_path, out, root = sys.argv[1:4]
data = json.load(open(matrix_path))
arms = []
for arm in data["arms"]:
    arm_id = arm["id"]
    subprocess.run(["bash", os.path.join(root, "scripts/build_arm.sh"), arm_id], check=False)
    summary_path = os.path.join(out, f"summary_{arm_id}.json")
    if os.path.isfile(summary_path):
        arms.append(json.load(open(summary_path)))
    else:
        arms.append({"arm_id": arm_id, "build_ok": False, "probe_ok": False, "digest": None})

shared = {}
for group in data.get("shared_backend_groups", []):
    backend = group["backend"]
    digests = []
    for aid in group["arm_ids"]:
        row = next((a for a in arms if a["arm_id"] == aid), None)
        if row and row.get("probe_ok") and row.get("digest") is not None:
            digests.append(row["digest"])
    shared[backend] = {
        "digests": digests,
        "identical": len(digests) > 0 and len(set(digests)) == 1,
        "arm_ids": group["arm_ids"],
    }

report = {
    "schema_version": 1,
    "arms": arms,
    "shared_backend_digests": shared,
}
open(os.path.join(out, "matrix_report.json"), "w").write(json.dumps(report, indent=2))
print(json.dumps({"wrote": os.path.join(out, "matrix_report.json"), "arms": len(arms)}))
PY
