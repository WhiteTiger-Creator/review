#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
"$ROOT/scripts/build.sh"
"$ROOT/scripts/run.sh"
test -f "$ROOT/output/skiff_report.json"
