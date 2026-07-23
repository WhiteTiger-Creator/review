#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
cd /app || true
python3 -m pytest -rA /tests/test_outputs.py
rc=$?
if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
