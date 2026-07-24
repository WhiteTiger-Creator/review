#!/bin/bash
set -euo pipefail
cd /app
cp /solution/fixed/kotlin/Model.kt src/main/kotlin/Model.kt
./build.sh
mkdir -p artifacts
./run.sh --panel data/panel.csv --out artifacts/elasticity.json
