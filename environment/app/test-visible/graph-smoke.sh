#!/usr/bin/env bash
set -euo pipefail

command -v dot
echo 'digraph G { a -> b }' | dot -Tsvg > /dev/null

WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT
mkdir -p "${WORKDIR}/output" "${WORKDIR}/events"
cp -a /app/data/events/. "${WORKDIR}/events/"
cp -a /app/config "${WORKDIR}/config"
cp /app/data/state/analysis-state.json "${WORKDIR}/state.json"

/app/bin/token-exposure-analyze \
  --events "${WORKDIR}/events" \
  --config "${WORKDIR}/config" \
  --regolib /app/opalib \
  --state "${WORKDIR}/state.json" \
  --output "${WORKDIR}/output"

REPORT="${WORKDIR}/output/token_exposure_report.json"
DOTFILE="${WORKDIR}/output/token_exposure_graph.dot"
test -s "${REPORT}"
test -s "${DOTFILE}"

head -n 1 "${DOTFILE}" | grep -q '^digraph'

# Quoted raw tenant IDs must not appear as DOT node identifiers.
if grep -E '^[[:space:]]*"tenant-[^"]+"[[:space:]]*\[' "${DOTFILE}" >/dev/null; then
  echo "graph-smoke: quoted raw tenant node identifiers are not allowed" >&2
  exit 1
fi

# At least one edge must use unquoted sanitized identifiers.
grep -E '^[[:space:]]*[A-Za-z0-9_]+[[:space:]]*->[[:space:]]*[A-Za-z0-9_]+' "${DOTFILE}" >/dev/null

python3 - "${REPORT}" "${DOTFILE}" <<'PY'
import json
import re
import sys

report_path, dot_path = sys.argv[1], sys.argv[2]
report = json.loads(open(report_path, encoding="utf-8").read())
dot = open(dot_path, encoding="utf-8").read()

ids = []
for node in report.get("nodes", []):
    ids.append(str(node.get("node_id", "")))
for edge in report.get("edges", []):
    ids.append(str(edge.get("source", "")))
    ids.append(str(edge.get("target", "")))

safe = re.compile(r"^[A-Za-z0-9_]+$")
for ident in ids:
    if not ident or not safe.match(ident):
        raise SystemExit(f"graph-smoke: non graph-safe identifier: {ident!r}")
    # Must appear as a bare identifier, not only inside a quoted string.
    if not re.search(rf'(?m)(^|[^A-Za-z0-9_"]){re.escape(ident)}([^A-Za-z0-9_"]|$)', dot):
        raise SystemExit(f"graph-smoke: identifier missing as DOT id: {ident}")

print("graph-id-contract-ok")
PY

python3 - "${REPORT}" "${DOTFILE}" "${WORKDIR}/events" <<'PY'
import json
import sys
from pathlib import Path

report_path, dot_path, events_dir = map(Path, sys.argv[1:])
report = json.loads(report_path.read_text(encoding="utf-8"))
report_blob = json.dumps(report, sort_keys=True)
dot_blob = dot_path.read_text(encoding="utf-8")
combined = report_blob + "\n" + dot_blob

fps = []
for shard in sorted(events_dir.glob("*.ndjson")):
    for line in shard.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        payload = ev.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        for key in (
            "token_fingerprint",
            "parent_token_fingerprint",
            "child_token_fingerprint",
            "access_token_fingerprint",
            "refresh_token_fingerprint",
        ):
            val = payload.get(key)
            if isinstance(val, str) and val:
                fps.append(val)

for fp in fps:
    if fp in combined:
        raise SystemExit(f"raw token fingerprint leaked: {fp}")
    if any(fp in json.dumps(item) for item in report.get("findings", [])):
        raise SystemExit(f"finding leaked raw fingerprint: {fp}")

print("redaction-contract-ok")
PY

echo graph-smoke-ok
