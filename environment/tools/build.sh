#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p tools
export GOCACHE="${GOCACHE:-/tmp/gocache}"
export GOPATH="${GOPATH:-/tmp/gopath}"
export GOTOOLCHAIN=local
export GOFLAGS=-mod=mod
export GOPROXY=off
go build -o tools/hv7.bin ./cmd/xbin
cat > tools/hv7 <<'EOF'
#!/bin/bash
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/tools/hv7.bin" "$@"
EOF
chmod +x tools/hv7 tools/hv7.bin
