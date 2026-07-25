#!/usr/bin/env bash
set -euo pipefail
sol_root="$(cd "$(dirname "$0")" && pwd -P)"
cd "$sol_root"

patch -d /app/environment -p0 --forward --batch < patches/a.patch
patch -d /app/environment -p0 --forward --batch < patches/b.patch
patch -d /app/environment -p0 --forward --batch < patches/c.patch

mkdir -p /app/output
/bin/bash /app/environment/scripts/build_workspace.sh

/app/environment/bin/etaengine stage --root /app/environment --scale-mode peak --graph-weight 0.005 --lane-weight 0.995
/app/environment/bin/etaengine finalize --root /app/environment
/app/environment/bin/etaengine commit --root /app/environment

/app/environment/bin/etaengine evaluate --root /app/environment --fixture batch_00 --family unit --seed 802 --out /app/output/run_doc.json
python3 /app/environment/scripts/assert_closed.py
