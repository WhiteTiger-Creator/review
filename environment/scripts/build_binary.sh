#!/usr/bin/env bash
set -euo pipefail
cd /app
export PATH="/usr/local/go/bin:${PATH}"
mkdir -p /app/bin /tmp/go-build
export GOCACHE=/tmp/go-build
for cmd in token-exposure-analyze inspect-event inspect-token-chain inspect-exposure-output; do
  go build -trimpath -o "/app/bin/${cmd}" "./cmd/${cmd}"
done
chmod +x /app/bin/*
