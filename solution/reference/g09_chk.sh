#!/usr/bin/env bash
set -euo pipefail

DOC="${1:-/app/output/proof_certificate_bundle.tar.json}"
OBL_ID="${2:-9}"

if [[ ! -f "$DOC" ]]; then
  echo "missing doc: $DOC" >&2
  exit 2
fi

violations=$(python3 - <<'PY' "$DOC"
import json
import pathlib
import sys

doc = json.load(open(sys.argv[1], encoding="utf-8"))
env = pathlib.Path("/app/environment")
algebra = json.loads((env / "k8m/pair_v7.json").read_text(encoding="utf-8"))
limits = (env / "k8m/lim_a763.toml").read_text(encoding="utf-8")
tolerance = 0
profile_word = 0
holdout_salt = 0
for line in limits.splitlines():
    if line.startswith("tolerance_band"):
        tolerance = int(line.partition("=")[2].strip(), 0)
    if line.startswith("profile_word"):
        raw = line.partition("=")[2].strip()
        profile_word = int(raw, 16) if raw.lower().startswith("0x") else int(raw, 0)
    if line.startswith("holdout_salt"):
        holdout_salt = int(line.partition("=")[2].strip(), 0)
rows = {(r["instance_key"], r["corpus_tag"]): r for r in doc.get("rows", [])}
violations = 0
mask = algebra.get("profile_mask", 0)
multiplier = max(1, int(algebra.get("stress_multiplier", 1)))
for pair in algebra["instance_pairs"]:
    a = rows.get((pair["key_a"], "a"))
    b = rows.get((pair["key_b"], "b"))
    if a is None or b is None:
        violations += 1
        continue
    mc = pair["cross_weight"] ^ (profile_word & mask) ^ holdout_salt
    scale = multiplier if int(a.get("lane_phase", 0)) >= 2 else 1
    duty_a = int(a["duty_cycles"])
    duty_b = int(b["duty_cycles"])
    if duty_b == 0 or duty_a % scale != 0:
        violations += 1
        continue
    raw_a = duty_a // scale
    derived_raw_a = max(0, raw_a - mc) // max(1, duty_b)
    expected = (derived_raw_a * duty_b + mc) * scale
    if abs(duty_a - expected) > tolerance:
        violations += 1
if int(doc.get("obligation_violations", 999)) != violations:
    violations += 1
print(violations)
PY
)

max_allowed=0
if [[ "$OBL_ID" == "9" ]]; then
  max_allowed=0
fi

if (( violations > max_allowed )); then
  echo "obligation ${OBL_ID} violations=${violations}" >&2
  exit 1
fi
echo "obligation ${OBL_ID} ok violations=${violations}"
