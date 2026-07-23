#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/cargo/bin:/opt/verifier/bin:/usr/local/bin:${PATH}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-/app/output/k_out.json}"
SITE_ROOT="${2:-/app/environment/k8}"
mkdir -p "$(dirname "$OUT")"
/usr/local/bin/wf_c --site-root "$SITE_ROOT" --fold /tmp/wf_stage_b/fold.json --out "$OUT" --env-root "$ROOT"
