#!/bin/sh
# Rebuild the slate CLI into /app/bin/slate.
set -eu

cd "$(dirname "$0")"
make clean >/dev/null 2>&1 || true
make all
./bin/slate version
