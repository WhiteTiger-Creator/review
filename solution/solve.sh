#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/app/skykingdom}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FILES_DIR="${SCRIPT_DIR}/files"

mkdir -p "${APP_ROOT}"
cp -f "${FILES_DIR}/go.mod" "${APP_ROOT}/go.mod"
cp -f "${FILES_DIR}/"*.go "${APP_ROOT}/"

# Preserve normative docs and scenarios already present in the image.
export PATH="/usr/local/go/bin:${PATH}"
cd "${APP_ROOT}"
go build -o skykingdom .
