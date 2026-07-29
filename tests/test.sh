#!/bin/bash
RESULT=1
trap 'exit "$RESULT"' EXIT
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
cd /app
/usr/bin/python3 -m pytest -q -rA --tb=short --no-header -p no:cacheprovider --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py
RESULT=$?
if [ "$RESULT" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
