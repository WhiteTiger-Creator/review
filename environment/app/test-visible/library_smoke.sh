#!/usr/bin/env bash
set -euo pipefail
LIBS="-f /app/lib/json.awk -f /app/lib/canonical.awk -f /app/lib/report.awk -f /app/lib/runtime.awk -f /app/lib/paths.awk -f /app/lib/users.awk -f /app/lib/providers.awk -f /app/lib/manifest.awk -f /app/lib/state.awk -f /app/lib/harborseal.awk"
out=$(gawk ${LIBS} -e 'BEGIN { hs_reset(); print "ok" }')
test "${out}" = "ok"
