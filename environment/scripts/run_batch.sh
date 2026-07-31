#!/bin/bash
set -euo pipefail

mkdir -p /app/output
rm -f /app/output/inventory_report.json /app/output/inv_scan.tsv /app/output/merged.tsv

bash /app/s2/q6/exec/t4_scan.sh /app/data/led_rows.tsv /app/etc/mesh_table.tsv /app/output/inv_scan.tsv
bash /app/m8/t1/exec/w2_run.sh /app/etc/frags/direct.list /app/etc/frags/indirect.list /app/docs/rank_buried.txt /app/output/merged.tsv
bash /app/v3/d4/exec/k9_run.sh /app/output/merged.tsv /app/data/gen_sheet.dat /app/etc/mesh_table.tsv /app/output/inventory_report.json
