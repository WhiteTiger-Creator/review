#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/go/bin:/go/bin:${PATH:-/usr/bin:/bin}"

ROOT="/app/opaline"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)/complete"

if [ ! -f "$ROOT/go.mod" ]; then
  echo "missing opaline module at $ROOT" >&2
  exit 1
fi

# Replace starter sources with the complete cartographer implementation.
cp "$SRC_DIR/board.go" "$ROOT/board.go"
cp "$SRC_DIR/cartographer.go" "$ROOT/cartographer.go"
cp "$SRC_DIR/validation.go" "$ROOT/validation.go"
cp "$SRC_DIR/engine.go" "$ROOT/engine.go"

# Remove starter stub units superseded by engine.go to avoid duplicate symbols.
rm -f \
  "$ROOT/state.go" \
  "$ROOT/movement.go" \
  "$ROOT/portals.go" \
  "$ROOT/routes.go" \
  "$ROOT/counting.go" \
  "$ROOT/canonical.go" \
  "$ROOT/metrics.go" \
  "$ROOT/trace.go"

gofmt -w "$ROOT"/*.go

cd "$ROOT"
GOWORK=off GOPROXY=off GOSUMDB=off go vet ./...
GOWORK=off GOPROXY=off GOSUMDB=off go build ./...
