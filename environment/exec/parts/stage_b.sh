#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/cargo/bin:/opt/verifier/bin:/usr/local/bin:${PATH}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SITE_ROOT="${1:-/app/environment/k8}"
/usr/local/bin/wf_b --site-root "$SITE_ROOT" --rows /tmp/wf_stage_a/rows.json --out /tmp/wf_stage_b/fold.json --env-root "$ROOT"
sqlite3 "$ROOT/var/k9.db" "SELECT COUNT(*) FROM arm_lineage;" > /tmp/wf_stage_b/lineage.count
