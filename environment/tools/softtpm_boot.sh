#!/usr/bin/env bash
set -euo pipefail
mkdir -p /app/var
/app/bin/lab_tpm reboot \
  --seed /app/environment/data/nv/counter_seed.bin \
  --nv-live /app/var/nv_live.bin
