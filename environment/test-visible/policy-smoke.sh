#!/usr/bin/env bash
set -euo pipefail
opa check /app/policy
echo policy-smoke-ok
