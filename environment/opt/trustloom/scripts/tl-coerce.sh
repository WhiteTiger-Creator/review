#!/bin/bash
# Lab coerce helper — forces labals back on and rebuilds.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo 'export GOFLAGS := -tags=labals' > "$ROOT/staging.mk"
cd "$ROOT"
go build -tags=labals -o bin/trustloom ./cmd/trustloom
