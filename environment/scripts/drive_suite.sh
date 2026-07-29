#!/usr/bin/env bash
set -euo pipefail
bash /app/environment/scripts/build_all.sh
/app/environment/bin/wave_sched --grid-full --out /app/output/storm_trace.json
