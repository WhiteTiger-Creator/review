#!/bin/bash
set -euo pipefail

export PATH="/usr/local/go/bin:/go/bin:${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"
export HOME="${HOME:-/root}"
export GOCACHE="${GOCACHE:-/opt/go-cache}"
export GOPROXY="${GOPROXY:-off}"
export GOSUMDB="${GOSUMDB:-off}"
export GOFLAGS="${GOFLAGS:--mod=mod}"
export GOTOOLCHAIN="${GOTOOLCHAIN:-local}"
export CGO_ENABLED="${CGO_ENABLED:-0}"

GO="${GO_BIN:-/usr/local/go/bin/go}"
DST="/app/opt/linkctl"
SRC="/solution/reference"

/bin/mkdir -p "$DST"
/bin/rm -f "$DST"/*.go
/bin/cp "$SRC/go.mod" "$DST/go.mod"
/bin/cp "$SRC/host.go" "$DST/host.go"
/bin/cp "$SRC/settle.go" "$DST/settle.go"
/bin/cp "$SRC/report.go" "$DST/report.go"
/bin/cp "$SRC/main.go" "$DST/main.go"

cd "$DST"
"$GO" build -o /app/bin/linkctl .
/app/bin/linkctl
