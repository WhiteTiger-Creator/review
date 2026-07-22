#!/bin/bash
set -euo pipefail

cd /app/environment

cp /solution/src/svd_impl.cpp src/svd_impl.cpp

rm -rf build
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j

test -x ./build/svd_solve || {
    echo "solve.sh: build did not produce ./build/svd_solve" >&2
    exit 1
}

./build/smoke_test || {
    echo "solve.sh: smoke_test failed" >&2
    exit 1
}

./build/svd_solve data/case_toy2x2.txt /tmp/svd_solve_smoke.out || {
    echo "solve.sh: svd_solve failed on case_toy2x2.txt" >&2
    exit 1
}

echo "solve.sh: build succeeded"
