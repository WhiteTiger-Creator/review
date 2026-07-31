#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
if [ "$PWD" = "/" ]; then echo "Error: No working directory set." >&2; exit 1; fi
export PYTHONSAFEPATH=1
TEST_DIR="${TEST_DIR:-/tests}"
python3 -m pytest -p no:cacheprovider --ctrf /logs/verifier/ctrf.json "${TEST_DIR}/test_outputs.py" -rA
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
