#!/usr/bin/env bash
set -euo pipefail

DOC=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --from)
      DOC="$2"; shift 2 ;;
    *)
      echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$DOC" || ! -f "$DOC" ]]; then
  echo "missing --from json" >&2
  exit 2
fi

python3 - <<'PY' "$DOC"
import json, sys
sys.path.insert(0, "/app/environment/tooling")
from digest_util import row_material_digest

path = sys.argv[1]
doc = json.load(open(path, encoding="utf-8"))
rows = doc.get("rows", [])
fp = doc.get("bank_fingerprint", "")
digest = row_material_digest(rows, fp)
if doc.get("replay_digest") != digest:
    print(f"replay digest mismatch: json={doc.get('replay_digest')} recomputed={digest}", file=sys.stderr)
    sys.exit(1)
if doc.get("arm_id") != "0763":
    print("arm_id must be 0763", file=sys.stderr)
    sys.exit(1)
if not fp or len(fp) != 8:
    print("bank_fingerprint missing or malformed", file=sys.stderr)
    sys.exit(1)
for row in rows:
    if row.get("lane_phase", 0) < 2:
        print("lane_phase below publish threshold", file=sys.stderr)
        sys.exit(1)
print(f"replay_digest ok {digest}")
PY

/app/environment/o9_chk/g09_chk.sh "$DOC" 9
