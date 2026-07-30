#!/usr/bin/env bash
set -euo pipefail
test -f /app/opalib/compat.rego
echo legacy-smoke-ok
