#!/usr/bin/env bash
set -euo pipefail
cd /app/environment
mkdir -p /app/environment/bin
CGO_ENABLED=0 go build -o /app/environment/bin/etaengine ./cmd/etaengine
