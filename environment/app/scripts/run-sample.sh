#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export SOFTHSM2_CONF="${SOFTHSM2_CONF:-$ROOT/config/softhsm2.conf}"
export PATH="/app/bin:${PATH}"
"$ROOT/scripts/reset-sample.sh"
exec signingd run --config "${1:-$ROOT/config/current.toml}"
