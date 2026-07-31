#!/usr/bin/env bash
set -euo pipefail

ENV_ROOT="/app/environment"
ARM=""
ALL_FIXTURES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --arm)
      ARM="$2"; shift 2 ;;
    --all-fixtures)
      ALL_FIXTURES=1; shift ;;
    *)
      echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ "$ARM" != "0763" ]]; then
  echo "unsupported arm: $ARM" >&2
  exit 2
fi

mkdir -p /app/output /app/output/stage
rm -f /app/output/proof_certificate_bundle.tar.json

cd "$ENV_ROOT"
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --target hs_driver -j"$(nproc)"
ARGS=()
if [[ "$ALL_FIXTURES" -eq 1 ]]; then
  ARGS+=(--all-fixtures)
fi
exec "$ENV_ROOT/build/hs_driver" "${ARGS[@]}"
