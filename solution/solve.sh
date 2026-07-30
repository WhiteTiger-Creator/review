#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

bash "$ROOT_DIR/apply_weave.sh"
bash "$ROOT_DIR/apply_splice.sh"
bash "$ROOT_DIR/apply_seal.sh"
bash "$ROOT_DIR/apply_trace.sh"
bash "$ROOT_DIR/apply_journal.sh"
bash "$ROOT_DIR/apply_glue.sh"

cd /app
cmake --build /app/build -j"$(nproc)"
/app/pvsim emit --scl /app/fixtures --corpora /app/corpora --annex /app/annex/slice_137.txt --out /app/runtime/dossier
/app/pvsim verify --fuzz --dossier /app/runtime/dossier --out /app/runtime/transcript
