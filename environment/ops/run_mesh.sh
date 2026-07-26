#!/bin/bash
# Operator entrypoint for the post-incident trust attestation.
set -euo pipefail
cd /app
OUT="${1:-/output/ceremony-ledger.json}"
cargo build -p trusteval --release
exec /app/target/release/trusteval attest --out "$OUT"
