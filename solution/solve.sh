#!/usr/bin/env bash
# Oracle: install known-good skykingdom binary + sources. Prefer the
# prebuilt linux/amd64 artifact so platform allow_internet=false cannot
# break a Go toolchain download (G-025).
set -euo pipefail

APP_ROOT="${APP_ROOT:-/app/skykingdom}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILES_DIR="${SCRIPT_DIR}/files"
BIN_OUT="${APP_ROOT}/skykingdom"
PREBUILT="${FILES_DIR}/skykingdom.linux-amd64"

export PATH="/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
export GOPROXY=off
export GOSUMDB=off
export GOTELEMETRY=off
export GOTOOLCHAIN=local
export CGO_ENABLED=0

mkdir -p "${APP_ROOT}"

# Refresh authoritative sources so verifier rebuilds stay correct.
# Preserve normative docs/scenarios already present in the image.
cp -f "${FILES_DIR}/go.mod" "${APP_ROOT}/go.mod"
cp -f "${FILES_DIR}/"*.go "${APP_ROOT}/"

if [[ -f "${PREBUILT}" ]]; then
  cp -f "${PREBUILT}" "${BIN_OUT}"
  chmod 755 "${BIN_OUT}"
else
  cd "${APP_ROOT}"
  go build -o "${BIN_OUT}" .
  chmod 755 "${BIN_OUT}"
fi

test -x "${BIN_OUT}"

# Smoke: eval without args should fail (usage / non-zero).
set +e
"${BIN_OUT}" >/tmp/skykingdom-smoke.out 2>/tmp/skykingdom-smoke.err
rc=$?
set -e
if [[ "${rc}" -eq 0 ]]; then
  echo "oracle smoke failed: expected non-zero exit without args" >&2
  exit 1
fi

echo "oracle installed ${BIN_OUT}"
