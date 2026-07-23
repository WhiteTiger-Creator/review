#!/bin/bash
set -euo pipefail

case_file=/app/cases/chain1-220390-220394.json
evidence=/app/audit/evidence
receipt=/app/audit/receipt.json

for area in acquire cli config receipt verify; do
  cp -f /solution/fixed/internal/"$area"/*.go /app/internal/"$area"/
done

cd /app
gofmt -w ./internal ./cmd
go test ./...
go build -trimpath -ldflags='-s -w' -o /usr/local/bin/beacon-audit ./cmd/beacon-audit

install -d -m 0750 /app/audit
beacon-audit acquire --case "$case_file" --directory "$evidence"
beacon-audit verify --case "$case_file" --directory "$evidence" --receipt "$receipt"

smoke=$(mktemp /tmp/beacon-receipt.XXXXXX)
trap 'rm -f "$smoke"' EXIT
beacon-audit verify --case "$case_file" --directory "$evidence" --receipt "$smoke"
cmp -s "$receipt" "$smoke"
test "$(find "$evidence" -maxdepth 1 -type f | wc -l)" -eq 6
