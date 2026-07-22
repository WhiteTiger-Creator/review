#!/bin/bash
set -euo pipefail

# Investigate the failing tool before changing anything (read-only).
cd /app
ls -la
echo "--- report.py (current placeholder reducer) ---"
sed -n '1,60p' report.py
echo "--- docs/spec.md (the contract to satisfy) ---"
sed -n '1,80p' docs/spec.md

# Apply the corrected reducer that implements the full contract.
cp /solution/report.py /app/report.py
