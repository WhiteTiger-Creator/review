#!/usr/bin/env bash
set -euo pipefail
test -f /app/policy/compat.rego
echo legacy-smoke-ok
