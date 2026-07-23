#!/bin/bash
set -euo pipefail
export PATH="/usr/local/cargo/bin:${PATH}"
cd /app

read_lab_value() {
    awk -F= -v key="$1" '
        $1 ~ "^[[:space:]]*" key "[[:space:]]*$" {
            value=$2
            sub(/^[[:space:]]*/, "", value)
            sub(/[[:space:]]*$/, "", value)
            gsub(/^"|"$/, "", value)
            print value
            exit
        }
    ' /app/config/lab.toml
}

# Rebuild publishers into /app/bin from the workspace (offline registry cache).
cargo build --release --locked --offline --bin apkfold --bin apk-board
mkdir -p /app/bin
install -m 0755 /app/target/release/apkfold /app/bin/apkfold
install -m 0755 /app/target/release/apk-board /app/bin/apk-board

if [ "$(read_lab_value replay_ready)" = "true" ]; then
    /app/bin/apkfold

    graph_generation="$(read_lab_value graph_generation)"
    expected_lock="$(read_lab_value graph_lock_sha256)"
    actual_lock="$(
        find /app/data/scenarios -maxdepth 1 -type f -name '*.json' -printf '%f\n' \
            | sort \
            | while read -r name; do cat "/app/data/scenarios/$name"; done \
            | sha256sum | awk '{print $1}'
    )"

    [ "$graph_generation" = "freeze-1" ] || {
        echo "graph generation must be freeze-1 for a replay-ready build" >&2
        exit 1
    }
    [ -n "$expected_lock" ] && [ "$actual_lock" = "$expected_lock" ] || {
        echo "sealed scenario lock mismatch" >&2
        exit 1
    }
    [ -f /app/data/runtime/index.json ] || {
        echo "runtime index missing after materialization" >&2
        exit 1
    }
    INDEX_LOCK_EXPECT="$actual_lock" python3 - <<'PY'
import json, os, sys
from pathlib import Path
idx = json.loads(Path("/app/data/runtime/index.json").read_text())
if "scenario_ids" not in idx or "lock_digest" not in idx:
    print("index.json must carry scenario_ids and lock_digest", file=sys.stderr)
    sys.exit(1)
if not isinstance(idx["scenario_ids"], list) or not idx["lock_digest"]:
    print("index.json scenario_ids/lock_digest malformed", file=sys.stderr)
    sys.exit(1)
if idx["lock_digest"] != os.environ["INDEX_LOCK_EXPECT"]:
    print("index.json lock_digest does not match sealed scenario corpus", file=sys.stderr)
    sys.exit(1)
PY
fi
