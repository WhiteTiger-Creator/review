#!/bin/bash
set -euo pipefail

cd /app
mkdir -p /app/output

SOL_DIR="${HARBOR_SOLUTION_DIR:-/solution}"

cp "${SOL_DIR}/go.mod" /app/go.mod
mkdir -p /app/internal/mesh /app/cmd/meshgate
cp "${SOL_DIR}/internal/mesh/mesh.go" /app/internal/mesh/mesh.go
cp "${SOL_DIR}/cmd/meshgate/main.go" /app/cmd/meshgate/main.go

go run /app/cmd/meshgate/main.go reconcile
