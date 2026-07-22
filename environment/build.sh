#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j

echo "build complete: build/svd_solve"
