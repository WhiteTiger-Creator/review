#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$ROOT/state"/* /output/signed /var/log/signing 2>/dev/null || true
mkdir -p "$ROOT/state" /output/signed/jobs /var/log/signing
touch "$ROOT/state/.keep"
echo "sample state reset"
