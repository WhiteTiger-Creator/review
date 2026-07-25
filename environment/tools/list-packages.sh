#!/bin/sh
# Print each registry package with its release count.
set -eu

BIN="${SLATE_BIN:-/app/bin/slate}"
REG="${SLATE_REGISTRY:-/app/registry}"

for f in "$REG"/*.json; do
    [ -e "$f" ] || continue
    stem="$(basename "$f" .json)"
    count="$("$BIN" versions "$stem" --registry "$REG" | wc -l | tr -d ' ')"
    printf '%s %s\n' "$stem" "$count"
done
