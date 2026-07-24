#!/bin/bash
set -o pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: no working directory set."
    exit 1
fi

rm -rf /app/outputs
mkdir -p /app/outputs
set +e
timeout 420s Rscript /app/analysis.R
analysis_status=$?
TEST_DIR="${TEST_DIR:-/tests}"
if [ "$analysis_status" -eq 0 ]; then
    /opt/test-venv/bin/python -I -m pytest -c "$TEST_DIR/pytest.ini" --rootdir=/tests --confcutdir=/tests --ctrf /logs/verifier/ctrf.json "$TEST_DIR/test_outputs.py" -v -rA
else
    echo "analysis.R failed with status $analysis_status"
    false
fi
test_status=$?
if [ "$test_status" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
