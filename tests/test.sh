#!/bin/bash
set -uo pipefail
export PATH="/usr/local/go/bin:/usr/local/bin:${PATH}"

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    mkdir -p /logs/verifier
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

mkdir -p /logs/verifier /app/output

cd /app && go build -o /app/bin/hanabi ./cmd/hanabi 2>&1
BUILD_RC=$?
if [ "$BUILD_RC" -ne 0 ]; then
    echo "Build failed with exit code $BUILD_RC"
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

rm -rf /app/output/*
/app/bin/hanabi

python3 -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -v -rA
rc=$?

if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
