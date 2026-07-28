#!/bin/bash
set -euo pipefail

database="$1"
rm -f "$database"
sqlite3 "$database" < /opt/soil/schema.sql

for file in /opt/soil/inputs/*_layers.tsv; do
    sqlite3 "$database" ".mode tabs" ".import --skip 1 $file layers"
done
for file in /opt/soil/inputs/*_forcing.tsv; do
    sqlite3 "$database" ".mode tabs" ".import --skip 1 $file forcing"
done
for file in /opt/soil/inputs/*_observations.tsv; do
    sqlite3 "$database" ".mode tabs" ".import --skip 1 $file observations"
done

sqlite3 "$database" "PRAGMA optimize;"
