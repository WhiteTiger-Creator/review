#!/usr/bin/env bash
set -euo pipefail
cp /solution/main.rs /app/src/main.rs
cd /app && cargo build --release
