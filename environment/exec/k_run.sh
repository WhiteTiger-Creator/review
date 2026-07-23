#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/cargo/bin:/opt/verifier/bin:/usr/local/bin:${PATH}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE_ROOT="/app/environment/k8"
OUT="/app/output/k_out.json"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --site-root) SITE_ROOT="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    *) shift ;;
  esac
done
bash "$ROOT/exec/parts/stage_a.sh" "$SITE_ROOT"
bash "$ROOT/exec/parts/stage_b.sh" "$SITE_ROOT"
bash "$ROOT/exec/parts/stage_c.sh" "$OUT" "$SITE_ROOT"
