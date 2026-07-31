#!/usr/bin/env bash
set -euo pipefail

install -m 0644 /solution/fixed/Makefile /app/Makefile
install -m 0644 /solution/fixed/gateway.c /app/src/gateway.c
install -m 0644 /solution/fixed/policy_baseline.c /app/src/policy_baseline.c
install -m 0644 /solution/fixed/policy_v3.c /app/src/policy_v3.c
install -m 0644 /solution/fixed/ledger-gateway.conf /app/config/ledger-gateway.conf
install -m 0644 /solution/fixed/manifest.txt /app/packaging/manifest.txt
install -m 0755 /solution/fixed/rebuild-runtime /app/tools/rebuild-runtime
install -m 0755 /solution/fixed/run-runtime /app/tools/run-runtime
install -m 0755 /solution/fixed/rollback-runtime /app/tools/rollback-runtime
install -m 0644 /solution/fixed/runtime-lib /app/tools/runtime-lib
/app/tools/rebuild-runtime /app/runtime
