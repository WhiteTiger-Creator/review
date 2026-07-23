#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/cargo/bin:/opt/verifier/bin:/usr/local/bin:${PATH}"
cd "$(dirname "$0")/.."
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/tmp/wf-target}"
cargo build --release -p wf
