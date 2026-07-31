#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/lib/k9_phase.sh"

mkdir -p /app/output
phase_k9 \
  "${1:-/app/output/merged.tsv}" \
  "${2:-/app/data/gen_sheet.dat}" \
  "${3:-/app/etc/mesh_table.tsv}" \
  "${4:-/app/output/inventory_report.json}"
