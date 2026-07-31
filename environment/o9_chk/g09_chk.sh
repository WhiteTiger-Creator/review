#!/usr/bin/env bash
set -euo pipefail

DOC="${1:-/app/output/proof_certificate_bundle.tar.json}"
OBL_ID="${2:-9}"

if [[ ! -f "$DOC" ]]; then
  echo "missing doc: $DOC" >&2
  exit 2
fi

violations=$(python3 - <<'PY' "$DOC"
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
print(int(doc.get("obligation_violations", 999)))
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
