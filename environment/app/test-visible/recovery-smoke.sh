#!/usr/bin/env bash
set -euo pipefail

work="$(mktemp -d /tmp/token-recovery-smoke-XXXXXX)"
clean="$(mktemp -d /tmp/token-recovery-clean-XXXXXX)"
trap 'rm -rf "$work" "$clean"' EXIT

cp -a /app/data/events "$work/events"
cp -a /app/config "$work/config"
cp /app/data/state/analysis-state.json "$work/state.json"
mkdir -p "$work/output"

cp -a /app/data/events "$clean/events"
cp -a /app/config "$clean/config"
cp /app/data/state/analysis-state.json "$clean/state.json"
mkdir -p "$clean/output"

run_analyze() {
  local dir="$1"
  shift
  env "$@" /app/bin/token-exposure-analyze \
    --events "$dir/events" \
    --config "$dir/config" \
    --regolib /app/opalib \
    --state "$dir/state.json" \
    --output "$dir/output"
}

run_analyze "$clean"
cp "$clean/output/token_exposure_report.json" "$clean/report.expected"
cp "$clean/output/token_exposure_graph.dot" "$clean/graph.expected"

set +e
run_analyze "$work" TOKEN_EXPOSURE_FAILPOINT=after_checkpoint >"$work/after_checkpoint.out" 2>"$work/after_checkpoint.err"
rc=$?
set -e
test "$rc" -ne 0
test ! -e "$work/output/token_exposure_report.json"
test ! -e "$work/output/token_exposure_graph.dot"

python3 - "$work/state.json" <<'PY'
import json
import sys
from pathlib import Path

state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert state.get("status") in {"CHECKPOINTED", "READY_TO_PUBLISH", "VALIDATING", "CORRELATING"}, state
assert state.get("checkpoint_id") or state.get("committed_shards"), state
assert state.get("evidence_fingerprint") or state.get("relevant_fingerprint"), state
PY

run_analyze "$work"

python3 - "$work/state.json" <<'PY'
import json
import sys
from pathlib import Path

state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert state.get("published") is True, state
assert state.get("resumed_from_checkpoint") is True, state
PY

cmp "$work/output/token_exposure_report.json" "$clean/report.expected"
cmp "$work/output/token_exposure_graph.dot" "$clean/graph.expected"

old_report="$work/old-report"
old_dot="$work/old-dot"
cp "$work/output/token_exposure_report.json" "$old_report"
cp "$work/output/token_exposure_graph.dot" "$old_dot"

python3 - "$work" <<'PY'
import json
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for path in sorted((root / "events").glob("*.ndjson")):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
rows.append({
    "schema_version": 2,
    "collector_id": "collector-east",
    "collector_sequence": 999,
    "observed_at": "2025-01-01T00:09:59Z",
    "event_id": "visible-atomic-forward",
    "event_type": "token_forwarded",
    "tenant_id": "tenant-a",
    "request_id": "req-visible-atomic",
    "trace_id": "tr-visible-atomic",
    "payload": {
        "exchange_id": "ex-visible-atomic",
        "token_fingerprint": "fp_visible_atomic_001",
        "proxy_id": "proxy-untrusted-1"
    }
})
shutil.rmtree(root / "events")
(root / "events").mkdir()
with (root / "events" / "visible-atomic.ndjson").open("w", encoding="utf-8") as f:
    for row in rows:
        f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
PY

set +e
run_analyze "$work" TOKEN_EXPOSURE_FAILPOINT=after_stage >"$work/after_stage.out" 2>"$work/after_stage.err"
rc=$?
set -e
test "$rc" -ne 0

cmp "$work/output/token_exposure_report.json" "$old_report"
cmp "$work/output/token_exposure_graph.dot" "$old_dot"
test ! -e "$work/output/.staging/token_exposure_report.json"
test ! -e "$work/output/.staging/token_exposure_graph.dot"

run_analyze "$work"
! cmp -s "$work/output/token_exposure_report.json" "$old_report"
! cmp -s "$work/output/token_exposure_graph.dot" "$old_dot"

/app/bin/inspect-exposure-output \
  --report "$work/output/token_exposure_report.json" \
  --dot "$work/output/token_exposure_graph.dot"

dot -Tplain "$work/output/token_exposure_graph.dot" >/dev/null

echo recovery-smoke-ok
