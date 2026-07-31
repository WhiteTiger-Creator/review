#!/bin/bash

emit_rows_json() {
  local out_json="$1"
  shift
  python3 - "$out_json" "$@" <<'PY'
import json, sys
out = sys.argv[1]
args = sys.argv[2:]
rows = []
i = 0
while i + 3 < len(args):
    rows.append({
        "lane_id": args[i],
        "edition_stamp": args[i + 1],
        "inventory_digest": args[i + 2],
        "selected_edition": args[i + 3],
    })
    i += 4
with open(out, "w", encoding="utf-8") as fh:
    json.dump({"rows": rows}, fh, indent=2)
    fh.write("\n")
PY
}
