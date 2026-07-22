#!/usr/bin/env bash
set -euo pipefail

DEST="${1:-/app/operator.mtx}"
URL_PRIMARY="https://sparse.tamu.edu/MM/Schmid/thermal2.tar.gz"
URL_MIRROR="https://suitesparse-collection-website.herokuapp.com/MM/Schmid/thermal2.tar.gz"
SHA256="02934a4b642b6829c33517e0b801b60ea894a6552c6cd7e3db6c709c776434ce"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if ! curl -fsSL --retry 3 -o "$WORK/op.tar.gz" "$URL_PRIMARY"; then
    curl -fsSL --retry 3 -o "$WORK/op.tar.gz" "$URL_MIRROR"
fi

echo "${SHA256}  ${WORK}/op.tar.gz" | sha256sum -c -
tar xzf "$WORK/op.tar.gz" -C "$WORK"
mv "$WORK/thermal2/thermal2.mtx" "$DEST"
echo "operator ready at $DEST"
