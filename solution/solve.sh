#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/cargo/bin:/opt/verifier/bin:/usr/local/bin:${PATH}"

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

patch -d /app -p1 < "$ROOT_DIR/patches/synth_core.patch"
patch -d /app -p1 < "$ROOT_DIR/patches/fold_core.patch"
patch -d /app -p1 < "$ROOT_DIR/patches/seal_core.patch"

cd /app/environment
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/tmp/wf-target}"
cargo build --release -p wf
cp /tmp/wf-target/release/wf_a /usr/local/bin/wf_a
cp /tmp/wf-target/release/wf_b /usr/local/bin/wf_b
cp /tmp/wf-target/release/wf_c /usr/local/bin/wf_c

rm -f /app/environment/var/.stage_scratch
mkdir -p /app/output
/app/environment/exec/k_run.sh --site-root /app/environment/k8 --out /app/output/k_out.json
