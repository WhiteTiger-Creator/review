#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app

cp "$ROOT_DIR/_extract_Makefile.snip" /app/Makefile
cp "$ROOT_DIR/_extract_main.c" /app/src/main.c
# routes.c is unchanged in milestone 1; environment starter is already correct.
cp "$ROOT_DIR/m1_db.c" /app/src/db.c
cp "$ROOT_DIR/oracle_index.html" /app/www/index.html
cp "$ROOT_DIR/m1_app.js" /app/www/app.js

make clean 2>/dev/null || true
make
