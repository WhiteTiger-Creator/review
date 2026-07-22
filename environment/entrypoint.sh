#!/usr/bin/env bash
set -euo pipefail

# Idempotent boot helper: prepare writable trees for nobody-based verifier runs.
# Called from tests/test.sh and solution/solve.sh (not via Dockerfile ENTRYPOINT).

mkdir -p /output /logs/verifier /logs/agent /app/.state
chmod 1777 /output /logs/verifier 2>/dev/null || true

# solve.sh runs as root; hand writable trees to nobody so permission-denial cases
# behave like the former non-root agent user without USER agent in the Dockerfile.
chown -R nobody:nogroup /app /output /app/.state
chmod -R a+rwX /app /output /app/.state
