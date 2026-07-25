#!/bin/bash
set -euo pipefail

TEST_DIR="${TEST_DIR:-/tests}"
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

# Invoke the verifier's interpreter by absolute path. The venv is root-owned and the agent runs
# unprivileged, so this resolves to the pytest baked into the image rather than anything the agent
# could have placed earlier on PATH.
set +e
/opt/verifier-venv/bin/pytest "$TEST_DIR/test_outputs.py" -rA -p no:cacheprovider \
    --ctrf /logs/verifier/ctrf.json

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
