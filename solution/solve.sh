#!/bin/bash
# Terminal-Bench Canary 8c4e1f9a
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app

patch -p1 < "${ROOT_DIR}/phase_b.patch"
patch -p1 < "${ROOT_DIR}/op_a.patch"
patch -p1 < "${ROOT_DIR}/reconcile_c.patch"

bash /app/environment/scripts/build.sh
bash /app/environment/scripts/replay.sh /app/environment/fixtures/f01.json
test -s /app/output/culvert_rank.yaml
