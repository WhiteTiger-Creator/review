#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    exit 1
fi

TEST_DIR="${TEST_DIR:-/tests}"

# Rebuild via cargo build is run inside pytest before executing test subprocesses
# --confcutdir prevents ancestor /conftest.py hijacks when rootdir resolves to /
pytest --confcutdir="$TEST_DIR" --ctrf /logs/verifier/ctrf.json "$TEST_DIR/test_outputs.py" -rA
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
