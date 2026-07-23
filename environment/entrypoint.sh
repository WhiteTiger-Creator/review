#!/usr/bin/env bash
set -euo pipefail
mkdir -p /app/output /logs/verifier /logs/agent
exec "$@"
