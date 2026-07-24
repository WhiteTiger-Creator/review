#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -lt 1 ]; then
  echo "usage: inspect.sh <pack-json>" >&2
  exit 2
fi
python3 - <<'PY' "$1"
import json, sys
pack = json.load(open(sys.argv[1], encoding="utf-8"))
print("case", pack.get("case_id"), "clusters", len(pack.get("cue_clusters", [])))
PY
