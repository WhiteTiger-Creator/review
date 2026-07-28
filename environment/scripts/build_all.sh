#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="/usr/local/go/bin:/opt/verifier/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
go build -C "$ROOT" -o /tmp/bn_run "$ROOT/cmd/bn_run"
test -x /tmp/bn_run
