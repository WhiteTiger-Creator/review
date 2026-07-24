#!/bin/bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/app}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCHES="${SCRIPT_DIR}/patches/src"

declare -A PATCH_MAP=(
  [plan/segment_plan.c]=plan/segment_plan.c
  [assemble/assemble_codewords.c]=assemble/assemble_codewords.c
  [protect/gf256.c]=protect/gf256.c
  [interleave/interleave_streams.c]=interleave/interleave_streams.c
  [matrix/matrix_build.c]=matrix/matrix_build.c
  [tournament/penalty_rules.c]=tournament/penalty_rules.c
)

for rel in "${!PATCH_MAP[@]}"; do
  cp -f "${PATCHES}/${rel}" "${APP_ROOT}/src/${rel}"
done
find "${APP_ROOT}" \( -name "*.c" -o -name "*.h" \) -exec touch {} +

cd "${APP_ROOT}"
cmake --build /app/build --target qr-composer
install -m 0755 /app/build/qr-composer /app/bin/qr-composer
test -x /app/bin/qr-composer

/app/bin/qr-composer init-store
/app/bin/qr-composer ingest-shipbatches
/app/bin/qr-composer plan-symbols
/app/bin/qr-composer assemble-codewords
/app/bin/qr-composer protect-blocks
/app/bin/qr-composer interleave-streams
/app/bin/qr-composer run-mask-tournament
/app/bin/qr-composer emit-labels
