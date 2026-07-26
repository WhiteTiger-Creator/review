#!/usr/bin/env bash
set -euo pipefail
dir="${1:-/output/profiles}"
for f in "${dir}"/*.cnf; do
  [ -f "$f" ] || continue
  mode="default"
  if grep -q 'fips=yes' "$f"; then mode="fips"; fi
  if grep -q 'hs_legacy' "$f"; then mode="legacy"; fi
  /app/bin/validate-openssl-profile --profile "$f" --mode "${mode}"
done
