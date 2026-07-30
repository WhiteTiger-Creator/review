#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p /app/bin

export PATH="/usr/local/go/bin:/usr/local/cargo/bin:${PATH:-}"
export CARGO_HOME="${CARGO_HOME:-/usr/local/cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-/usr/local/rustup}"
export GOPATH="${GOPATH:-/go}"

cd "$ROOT"
go build -o /app/bin/cabrelay ./cmd/cabrelay
cargo build --release --manifest-path "$ROOT/Cargo.toml" --offline
install -m 0755 "$ROOT/target/release/sealwalk" /app/bin/sealwalk
install -m 0755 "$ROOT/target/release/gatemode" /app/bin/gatemode
