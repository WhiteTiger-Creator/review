#!/usr/bin/env bash
# Wipes the database so the server starts fresh with seed data on next boot.
set -euo pipefail
DB_PATH="${DB_PATH:-/opt/jobqueue/jobs.db}"
rm -f "$DB_PATH" "$DB_PATH-wal" "$DB_PATH-shm"
echo "Database reset: $DB_PATH"
