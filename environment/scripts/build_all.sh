#!/usr/bin/env bash
set -euo pipefail
cd /app/environment
export PATH="/usr/local/go/bin:${PATH}"
go build -o /app/environment/bin/wave_sched ./cmd/wave_sched
