#!/usr/bin/env bash
set -euo pipefail
name="${1:?profile id}"
bash /app/environment/tools/softtpm_boot.sh
/app/bin/lab_tpm unseal \
  --blob /app/output/pol_blob.bin \
  --fixture "/app/environment/data/profiles/${name}.json" \
  --nv-live /app/var/nv_live.bin
