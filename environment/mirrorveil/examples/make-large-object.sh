#!/bin/bash
set -euo pipefail

ROOT=/srv/mirrorveil
SIZE=$((6 * 1024 * 1024))
HOSTS=(releases.aurora.invalid releases.basalt.invalid)
ORIGINS=(primary secondary)

# Deterministic six MiB payload: repeating 256-byte pattern keyed by host.
make_blob() {
  local host="$1"
  local out="$2"
  local pattern
  pattern="$(printf 'MVLARGE:%s:' "${host}"; printf 'ABCDEFGHIJKLMNOPQRSTUVWXYZ012345')"
  python3 - "${SIZE}" "${pattern}" "${out}" <<'PY'
import sys
size = int(sys.argv[1])
pattern = sys.argv[2].encode()
out = sys.argv[3]
buf = (pattern * ((size // len(pattern)) + 1))[:size]
with open(out, "wb") as fh:
    fh.write(buf)
PY
}

for origin in "${ORIGINS[@]}"; do
  for host in "${HOSTS[@]}"; do
    dest="${ROOT}/origins/${origin}/${host}/large"
    mkdir -p "${dest}"
    make_blob "${host}" "${dest}/archive.bin"
  done
done

echo "wrote deterministic ${SIZE}-byte large artifacts"
