#!/bin/bash
set -euo pipefail

ROOT=/srv/mirrorveil
# shellcheck source=/dev/null
source "${ROOT}/policy/topology.conf"

"${ROOT}/bin/start-cache-stack"
"${ROOT}/bin/wait-for-cache" stack-ready
"${ROOT}/bin/inspect-cache"
code="$(curl -sS -o /tmp/mirrorveil-probe-body -w '%{http_code}' \
  -H "Host: releases.aurora.invalid" \
  "http://${CACHE_ADDR}:${CACHE_PORT}/artifacts/stable/toolkit.tar")"
echo "sample_http_code=${code}"
"${ROOT}/bin/stop-cache-stack"
echo "verify-stack completed"
