#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app

cp "$ROOT_DIR/oracle_routes.c" /app/src/routes.c
cp "$ROOT_DIR/oracle_db.c" /app/src/db.c

make clean 2>/dev/null || true
make
