#!/usr/bin/env bash
set -euo pipefail
opa check /app/opalib
echo opalib-smoke-ok
