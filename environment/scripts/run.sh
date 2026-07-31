#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export SKIFF_ROOT="$ROOT"
mkdir -p "$ROOT/output"
"$ROOT/bin/skiff" "$ROOT"
