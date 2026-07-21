#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

bash apply_v3_read_scale.sh
bash apply_k8_rank_slot.sh
bash apply_q5_pack_stamp.sh
bash apply_m14_lane_store.sh
bash apply_c9_pass_gate.sh
bash apply_f12_drift_total.sh
bash apply_n21_header.sh

cmake -S /app/environment -B /app/build -G Ninja
ninja -C /app/build forge_emit
