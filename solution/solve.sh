#!/usr/bin/env bash
set -euo pipefail
install -m 0755 "$(dirname "$0")/analysis.R" /app/analysis.R
DATA_PATH="${DATA_PATH:-/app/data}" OUTPUT_PATH="${OUTPUT_PATH:-/app/output}" Rscript /app/analysis.R
