#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

say() { printf '[oracle] %s\n' "$1"; }

say "stage 1: validate reference bundle patches"
bash "$ROOT_DIR/preflight_frontier.sh" reference

say "stage 2: install repaired frontier sources"
install -m 0644 "$ROOT_DIR/reference/q2_w3.cpp" /app/environment/r3k/src/q2_w3.cpp
install -m 0644 "$ROOT_DIR/reference/reloc_fold.cpp" /app/environment/w7p/src/reloc_fold.cpp
install -m 0644 "$ROOT_DIR/reference/v8_emit.cpp" /app/environment/j2n/src/v8_emit.cpp
install -m 0644 "$ROOT_DIR/reference/bank_cache.cpp" /app/environment/s4d/src/bank_cache.cpp
install -m 0644 "$ROOT_DIR/reference/main.cpp" /app/environment/hs_driver/src/main.cpp
install -m 0755 "$ROOT_DIR/reference/g09_chk.sh" /app/environment/o9_chk/g09_chk.sh

say "stage 3: confirm installed frontier symbols"
bash "$ROOT_DIR/preflight_frontier.sh" installed

say "stage 4: rebuild hs_driver and publish graded bundle"
rm -rf /app/output/proof_certificate_bundle.tar.json /app/output/stage
mkdir -p /app/output
cd /app/environment
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --target hs_driver -j"$(nproc)"
/app/environment/exec/run_hs_cycle.sh --arm 0763 --all-fixtures

say "stage 5: validate regenerated bundle contract"
bash "$ROOT_DIR/preflight_frontier.sh" output

say "stage 6: independent obligation replay"
/app/environment/tooling/verify_ob9_d9.sh --from /app/output/proof_certificate_bundle.tar.json

say "finished"
