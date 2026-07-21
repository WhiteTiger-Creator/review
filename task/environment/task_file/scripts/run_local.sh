#!/usr/bin/env bash
# Build and run the server locally.
set -euo pipefail
cd "$(dirname "$0")/.."
CGO_ENABLED=1 go build -o jobqueue .
DB_PATH="${DB_PATH:-/opt/jobqueue/jobs.db}" PORT="${PORT:-8080}" ./jobqueue
