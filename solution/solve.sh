#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd /app/environment
patch -p1 < "$ROOT_DIR/patches/01-k2.patch"
patch -p1 < "$ROOT_DIR/patches/02-m4.patch"
patch -p1 < "$ROOT_DIR/patches/03-w3.patch"
patch -p1 < "$ROOT_DIR/patches/04-r7.patch"
patch -p1 < "$ROOT_DIR/patches/05-n5.patch"

make -C /app/environment install

bash /app/environment/scripts/run_matrix.sh baseline_cold
bash /app/environment/scripts/run_matrix.sh migrate_load
bash /app/environment/scripts/run_matrix.sh rebuild_corpus
bash /app/environment/scripts/run_matrix.sh v2_idempotent
bash /app/environment/scripts/run_matrix.sh twin_mass
bash /app/environment/scripts/run_matrix.sh hybrid_halt
bash /app/environment/scripts/run_matrix.sh torn_resume
bash /app/environment/scripts/run_matrix.sh gen_bump_ceiling
bash /app/environment/scripts/run_matrix.sh assess_after_migrate
bash /app/environment/scripts/run_matrix.sh double_fence_migrate
bash /app/environment/scripts/run_matrix.sh halt_twin_order
