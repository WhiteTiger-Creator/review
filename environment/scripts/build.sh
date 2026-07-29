#!/usr/bin/env bash
set -euo pipefail
cd /app
export CARGO_HOME="${CARGO_HOME:-/usr/local/cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-/usr/local/rustup}"
export PATH="${CARGO_HOME}/bin:${PATH}"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/app/target}"
cargo build --release -p undercroft_fairness
mkdir -p /app/bin /app/output /app/state
install -m 0755 "${CARGO_TARGET_DIR}/release/undercroft_fairness" /app/bin/undercroft-fairness
