#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACK=""
OUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack)
      PACK="$2"
      shift 2
      ;;
    --out)
      OUT="$2"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
  esac
done
if [[ -z "$PACK" || -z "$OUT" ]]; then
  echo "usage: run_desk.sh --pack <path> --out <path>" >&2
  exit 2
fi
bash "$ROOT/scripts/build_n4k.sh"
node "$ROOT/dist/src/main.js" --pack "$PACK" --out "$OUT"
