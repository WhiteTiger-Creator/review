#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

TEST_DIR="${TEST_DIR:-/tests}"
if [ "$PWD" = "/" ]; then
  echo "Warning: verifier started at /; switching to $TEST_DIR"
fi

cd "$TEST_DIR"
PYTHONSAFEPATH=1 PYTHONNOUSERSITE=1 PYTHONPATH=/opt/harbor-verifier \
  python3 -m pytest -p harbor_ctrf_plugin --ctrf /logs/verifier/ctrf.json "$TEST_DIR/test_outputs.py" -rA
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
