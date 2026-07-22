#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/apnea_hmm.cpp" /app/src/apnea_hmm.cpp
/app/scripts/run-triage.sh
