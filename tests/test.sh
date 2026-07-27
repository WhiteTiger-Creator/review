#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/cargo/bin:/usr/local/rustup/bin:/root/.cargo/bin:${HOME:-/root}/.cargo/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

fail() {
  echo 0 > /logs/verifier/reward.txt
  echo "$1" >&2
  exit 1
}

if [[ "${PWD:-/}" == "/" ]]; then
  fail "Error: no working directory configured"
fi

if [[ ! -f /app/Cargo.toml ]]; then
  fail "Error: /app/Cargo.toml missing"
fi

if ! command -v cargo >/dev/null 2>&1; then
  fail "Error: cargo is unavailable"
fi

cd /app
rm -rf /app/target

if ! cargo build --release --locked --offline; then
  fail "Error: candidate Cargo build failed"
fi

BIN=""
for candidate in /app/target/release/msrv-lock-recovery-planner; do
  if [[ -x "$candidate" ]]; then
    BIN="$candidate"
    break
  fi
done
if [[ -z "$BIN" ]]; then
  BIN="$(find /app/target/release -maxdepth 1 -type f -perm -111 ! -name '*.d' ! -name '.*' | head -n 1 || true)"
fi
if [[ -z "${BIN}" || ! -x "${BIN}" ]]; then
  fail "Error: release binary missing"
fi

export MSRV_LOCK_RECOVERY_PLANNER_BIN="$BIN"
export TEST_DIR="${TEST_DIR:-/tests}"
export APP_DATA_DIR="${APP_DATA_DIR:-/app/data}"
export APP_OUTPUT_REPORT="${APP_OUTPUT_REPORT:-/app/output/report.json}"

set +e
collected="$(
  python3 -m pytest \
    -o cache_dir=/tmp/pytest_cache \
    --collect-only -q \
    "$TEST_DIR/test_outputs.py" 2>&1
)"
collect_rc=$?
set -e

if [[ "$collect_rc" -ne 0 ]]; then
  fail "Error: pytest collection failed: ${collected}"
fi

count="$(
  printf '%s\n' "$collected" \
    | python3 -c 'import sys; print(sum(1 for line in sys.stdin if "test_" in line and "::" in line))'
)"

if [[ "$count" != "23" ]]; then
  fail "Error: expected exactly 23 pytest tests, found ${count}"
fi

set +e
python3 -m pytest \
  -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json \
  "$TEST_DIR/test_outputs.py" \
  -rA
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
