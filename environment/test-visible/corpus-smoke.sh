#!/usr/bin/env bash
set -euo pipefail
test -d /app/data/events
wc -l /app/data/events/*.ndjson
echo corpus-smoke-ok
