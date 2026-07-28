#!/bin/sh
# Smoke the shipped subcommands: every package prints and every manifest parses.
set -eu

BIN="${SLATE_BIN:-/app/bin/slate}"
REG="${SLATE_REGISTRY:-/app/registry}"
MAN="${SLATE_MANIFESTS:-/app/manifests}"

"$BIN" version
"$BIN" audit --registry "$REG"
for f in "$REG"/*.json; do
    [ -e "$f" ] || continue
    stem="$(basename "$f" .json)"
    "$BIN" show "$stem" --registry "$REG" >/dev/null
    "$BIN" versions "$stem" --registry "$REG" >/dev/null
    printf 'ok package %s\n' "$stem"
done
for f in "$MAN"/*.slate; do
    [ -e "$f" ] || continue
    stem="$(basename "$f" .slate)"
    "$BIN" manifest "$stem" --registry "$REG" --manifests "$MAN" >/dev/null
    printf 'ok project %s\n' "$stem"
done
