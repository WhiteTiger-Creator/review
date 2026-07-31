#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="/usr/local/go/bin:${PATH:-}"
cd "$ROOT"
GOFLAGS=-mod=mod go test ./internal/band/ ./internal/feed/
