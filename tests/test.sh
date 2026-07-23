#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

fail() {
    echo "$1" >&2
    echo 0 > /logs/verifier/reward.txt
    exit 1
}

if [ "$PWD" = "/" ]; then
    fail "Error: no working directory configured."
fi

CARGO_BIN="$(command -v cargo || true)"
if [ -z "$CARGO_BIN" ] && [ -x /usr/local/bin/cargo ]; then
    CARGO_BIN=/usr/local/bin/cargo
fi
if [ -z "$CARGO_BIN" ] && [ -x /usr/local/cargo/bin/cargo ]; then
    CARGO_BIN=/usr/local/cargo/bin/cargo
fi
if [ -z "$CARGO_BIN" ] || [ ! -x "$CARGO_BIN" ]; then
    fail "Cargo is unavailable."
fi

if ! command -v python3 >/dev/null 2>&1; then
    fail "python3 is unavailable."
fi

rm -rf /app/target
rm -f /app/output/bootstrap.sql /app/output/bootstrap_plan.json

if ! (
    cd /app
    "$CARGO_BIN" build --release --locked --offline
) > /tmp/candidate_build.log 2>&1; then
    echo "Candidate release build failed." >&2
    cat /tmp/candidate_build.log >&2
    fail "Candidate release build failed."
fi

CANDIDATE_BIN=/app/target/release/pg-bootstrap
if [ ! -x "$CANDIDATE_BIN" ]; then
    fail "Expected native release binary is missing: $CANDIDATE_BIN"
fi

if [ ! -f /tests/run_candidate_isolated.sh ]; then
    fail "candidate-isolation setup failure: missing /tests/run_candidate_isolated.sh"
fi
ISOLATION_WRAPPER=/tmp/run_candidate_isolated.sh
tr -d '\r' < /tests/run_candidate_isolated.sh > "$ISOLATION_WRAPPER"
chmod +x "$ISOLATION_WRAPPER"

for deny in /tests /solution /logs/verifier; do
    if [ -e "$deny" ]; then
        chmod o-rwx "$deny" 2>/dev/null || true
    fi
done

if ! CANDIDATE_ISOLATION_SELFCHECK=1 bash "$ISOLATION_WRAPPER" "$CANDIDATE_BIN" -- plan >/tmp/isolation_selfcheck.log 2>&1; then
    echo "Candidate isolation self-check failed." >&2
    cat /tmp/isolation_selfcheck.log >&2
    fail "candidate isolation self-check failure"
fi
if ! grep -q ISOLATION_OK /tmp/isolation_selfcheck.log; then
    cat /tmp/isolation_selfcheck.log >&2
    fail "candidate isolation self-check failure"
fi

export PG_BOOTSTRAP_BIN="$CANDIDATE_BIN"
export ISOLATION_WRAPPER="$ISOLATION_WRAPPER"
export PYTHONPATH=/tests

COLLECT_OUTPUT="$(
    python3 -I -m pytest \
        --confcutdir=/tests \
        -o cache_dir=/tmp/pytest_cache \
        --collect-only -q \
        /tests/test_outputs.py 2>&1
)"
COLLECT_RC=$?
printf '%s\n' "$COLLECT_OUTPUT"
if [ "$COLLECT_RC" -ne 0 ]; then
    fail "pytest collection failure"
fi
if ! printf '%s\n' "$COLLECT_OUTPUT" | grep -Eq '30 tests collected|30 collected'; then
    fail "Expected exactly 30 candidate-facing tests."
fi

python3 -I -m pytest \
    --confcutdir=/tests \
    -o cache_dir=/tmp/pytest_cache \
    --ctrf /logs/verifier/ctrf.json \
    /tests/test_outputs.py \
    -rA
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
