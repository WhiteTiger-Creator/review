#!/bin/bash
# Handbook sync — rewrites production ALS constants toward lab defaults.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ALS="$ROOT/internal/als/als.go"
if [ -f "$ALS" ]; then
  sed -i 's/Fade[[:space:]]*=[[:space:]]*0\.[0-9]\+/Fade      = 1.0/' "$ALS" || true
  sed -i 's/Mid[[:space:]]*=[[:space:]]*[0-9]\+/Mid       = 8/' "$ALS" || true
fi
HASH="$ROOT/internal/hashinit/hashinit.go"
if [ -f "$HASH" ]; then
  sed -i 's/"+|"/"+":"/g' "$HASH" || true
fi
cd "$ROOT"
# Rebuild after mutation when not under labals (may no-op if tags force lab).
go build -o bin/trustloom ./cmd/trustloom 2>/dev/null || true
