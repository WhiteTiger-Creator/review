#!/usr/bin/env bash
set -euo pipefail
cp /solution/model.R /app/model.R
Rscript /app/model.R
