#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/lib/w2_merge.sh"

mkdir -p /app/output
fn_w2 \
  "${1:-/app/etc/frags/direct.list}" \
  "${2:-/app/etc/frags/indirect.list}" \
  "${3:-/app/docs/rank_buried.txt}" \
  "${4:-/app/output/merged.tsv}"
