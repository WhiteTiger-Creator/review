#!/bin/bash
set -euo pipefail
sd="$(cd "$(dirname "$0")" && pwd)"
cp "$sd/go.mod" /app/go.mod
cp "$sd/main.go" /app/cmd/lockout-guard/main.go
go build -trimpath -o /app/bin/lockout-guard ./cmd/lockout-guard
/app/bin/lockout-guard
