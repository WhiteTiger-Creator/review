#!/usr/bin/env bash
set -euo pipefail

TARGET="/app/emberline/src/main/java/dev/emberline/game/TurnResolver.java"
SOURCE="/solution/TurnResolver.java"

if [[ ! -f "$SOURCE" ]]; then
  # Harbor mounts solution at /solution; fall back to script-adjacent copy.
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  SOURCE="${SCRIPT_DIR}/TurnResolver.java"
fi

if [[ ! -f "$SOURCE" ]]; then
  echo "oracle TurnResolver.java not found" >&2
  exit 1
fi

cp "$SOURCE" "$TARGET"
chmod 644 "$TARGET"

cd /app/emberline
make clean
make
