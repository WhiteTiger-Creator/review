#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/cargo/bin:/opt/verifier/bin:/usr/local/bin:${PATH}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SITE_ROOT="${1:-/app/environment/k8}"
mkdir -p /tmp/wf_stage_a
/usr/local/bin/wf_a --site-root "$SITE_ROOT" --out /tmp/wf_stage_a/rows.json
cat /app/environment/etc/version.txt >/tmp/wf_stage_a/stamp.txt
