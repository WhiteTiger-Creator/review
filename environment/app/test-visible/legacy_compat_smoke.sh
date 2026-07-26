#!/usr/bin/env bash
set -euo pipefail
tmp=$(mktemp -d)
gawk -f /app/lib/json.awk -f /app/lib/canonical.awk -f /app/lib/report.awk -f /app/lib/runtime.awk \
  -f /app/lib/paths.awk -f /app/lib/users.awk -f /app/lib/providers.awk -f /app/lib/manifest.awk \
  -f /app/lib/state.awk -f /app/lib/harborseal.awk \
  -v bundle="/app/data/oci/legacy-proxy" \
  -v tmpdir="${tmp}" \
  -e 'BEGIN { hs_reset(); hs_configure("", "migration_instant", "2026-04-01T00:00:00Z"); hs_load_report_index("/app/data/report/decision-index.json"); hs_resolve_service(bundle, bundle "/config.json", tmpdir) }'
test -s "${tmp}/legacy-proxy-api.cnf"
rm -rf "${tmp}"
