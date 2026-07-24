#!/usr/bin/env bash
set -euo pipefail

cd /solution
test -d /app/environment
bash patch_tableq5.sh
bash patch_k7m.sh
bash patch_n3p.sh
bash patch_frameq7.sh
bash patch_q2s.sh
make -C /app/environment
/app/exec/diff_run --case 352 --mode direct
test -f /app/output/diff_replay_dossier.json
printf '[solve] done\n'
