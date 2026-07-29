#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "$ROOT_DIR/patch_a.sh"

bash "$ROOT_DIR/patch_b.sh"

bash "$ROOT_DIR/patch_c.sh"

chmod +x /app/environment/run_ferric_drv
cd /app/environment
./run_ferric_drv
