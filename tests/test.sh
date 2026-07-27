#!/bin/bash
set -euo pipefail

TEST_DIR="${TEST_DIR:-/tests}"
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

export PATH="/opt/verifier-venv/bin:$PATH"

set +e
pytest "$TEST_DIR/test_outputs.py" -rA -p no:cacheprovider \
    --ctrf /logs/verifier/ctrf.json

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
