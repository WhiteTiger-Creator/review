#!/bin/bash
# Host-side oracle: apply solve.sh with local paths (no Docker).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TR="$ROOT/environment/trust-remediator"
DATA="$ROOT/environment/data"
OUT="$ROOT/.host_output"
mkdir -p "$OUT" "$TR/build"
if [[ -f "$ROOT/tests/data/access/held_out.journal" ]]; then
  cp "$ROOT/tests/data/access/held_out.journal" "$DATA/access/held_out.journal"
fi
sed \
  -e "s|/app/trust-remediator|$TR|g" \
  -e "s|/app/data|$DATA|g" \
  -e "s|/app/output|$OUT|g" \
  "$ROOT/solution/solve.sh" | bash
