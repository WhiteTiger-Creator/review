#!/bin/bash
set -euo pipefail

solution_root="$(cd "$(dirname "$0")" && pwd)"

cp "$solution_root/backfill_governance.cpp" /app/work/ceph/src/backfill_governance.cpp
cp "$solution_root/ceph.conf" /app/work/ceph/etc/ceph.conf
cp "$solution_root/fullness.conf" /app/work/ceph/etc/fullness.conf
cp "$solution_root/reweight.conf" /app/work/ceph/etc/reweight.conf
cp "$solution_root/recovery.conf" /app/work/ceph/etc/recovery.conf
cp "$solution_root/flags.conf" /app/work/ceph/etc/flags.conf
make -C /app/work/ceph clean all
ceph-conf --conf /app/work/ceph/etc/ceph.conf --name osd.0 --lookup osd_max_backfills >/dev/null
