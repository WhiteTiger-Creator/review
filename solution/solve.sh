#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORACLE_SRC="${SCRIPT_DIR}/oracle_src"
APP_DIR="/app"

export PATH="/usr/local/cargo/bin:/root/.cargo/bin:${PATH:-}"

command -v cargo >/dev/null 2>&1 || {
  echo "error: cargo not found" >&2
  exit 1
}

test -d "${ORACLE_SRC}/src" || {
  echo "error: Oracle source missing" >&2
  exit 1
}

test -f "${ORACLE_SRC}/Cargo.toml" || {
  echo "error: Oracle Cargo.toml missing" >&2
  exit 1
}

test -f "${ORACLE_SRC}/Cargo.lock" || {
  echo "error: Oracle Cargo.lock missing" >&2
  exit 1
}

rm -rf "$APP_DIR/src"
rm -rf "$APP_DIR/target"

cp -a "${ORACLE_SRC}/src" "$APP_DIR/src"
cp "${ORACLE_SRC}/Cargo.toml" "$APP_DIR/Cargo.toml"
cp "${ORACLE_SRC}/Cargo.lock" "$APP_DIR/Cargo.lock"

test -d "$APP_DIR/vendor" || {
  echo "error: image-provided vendor directory missing" >&2
  exit 1
}

test -f "$APP_DIR/.cargo/config.toml" || {
  echo "error: image-provided Cargo configuration missing" >&2
  exit 1
}

mkdir -p /app/output
rm -f /app/output/report.json
rm -f /app/output/report.json.tmp

cd /app
cargo build --release --locked --offline

BIN="/app/target/release/msrv-lock-recovery-planner"
test -x "$BIN" || {
  echo "error: Oracle binary missing: $BIN" >&2
  exit 1
}

"$BIN" --data-dir /app/data --output /app/output/report.json

python3 - <<'PY'
import json
from pathlib import Path

path = Path("/app/output/report.json")
assert path.is_file() and path.stat().st_size > 0
data = json.loads(path.read_text(encoding="utf-8"))
required = [
    "request_rows",
    "package_selection_rows",
    "patch_rows",
    "source_replacement_rows",
    "lock_entry_rows",
    "invalidation_rows",
    "conflict_rows",
    "summary",
]
assert list(data.keys()) == required, list(data.keys())
assert data["summary"]["request_count"] >= 1
print("oracle smoke ok")
PY
