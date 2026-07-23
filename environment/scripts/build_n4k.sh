#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ -x "$ROOT/node_modules/.bin/tsc" ]; then
  "$ROOT/node_modules/.bin/tsc" -p tsconfig.json
elif command -v tsc >/dev/null 2>&1; then
  tsc -p tsconfig.json
else
  npx --yes typescript@5.7.3 tsc -p tsconfig.json
fi
