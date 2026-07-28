#!/usr/bin/env bash
mkdir -p /logs/verifier
cd /tests 2>/dev/null || cd "$(dirname "$0")" 2>/dev/null || true
python3 -m pytest -rA --maxfail=1 -p no:cacheprovider --confcutdir=/tests -c /tests/pytest.ini --ctrf /logs/verifier/ctrf.json test_outputs.py
status=$?
if [ "$status" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
