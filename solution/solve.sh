#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/cargo/bin:/app/bin:${PATH}"

APP_ROOT="${APP_ROOT:-/app}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "${SCRIPT_DIR}/files/rng.rs" "${APP_ROOT}/src/rng.rs"
cp "${SCRIPT_DIR}/files/score.rs" "${APP_ROOT}/src/score.rs"
cp "${SCRIPT_DIR}/files/train.rs" "${APP_ROOT}/src/train.rs"
cp "${SCRIPT_DIR}/files/persist.rs" "${APP_ROOT}/src/persist.rs"
cp "${SCRIPT_DIR}/files/metrics.rs" "${APP_ROOT}/src/metrics.rs"

cd "${APP_ROOT}"
cargo build --release --locked
mkdir -p /app/bin /app/state /app/output
cp /app/target/release/fmctl /app/bin/fmctl
test -x /app/bin/fmctl
