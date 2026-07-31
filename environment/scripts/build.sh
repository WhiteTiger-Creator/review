#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="/usr/local/cargo/bin:/usr/local/go/bin:${PATH:-}"
export CGO_ENABLED=1
export RUSTUP_HOME="${RUSTUP_HOME:-/usr/local/rustup}"
export CARGO_HOME="${CARGO_HOME:-/usr/local/cargo}"

cd "$ROOT/orb-rs"
cargo build --release --locked

cd "$ROOT"
mkdir -p bin
GOFLAGS=-mod=mod CGO_ENABLED=1 go build -trimpath -buildvcs=false -o bin/skiff ./cmd/skiff
