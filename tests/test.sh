#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
cd /tests
PYTHONPATH= PYTHONSAFEPATH=1 python3 -P -m pytest -rA -p no:cacheprovider --confcutdir=/tests /tests/test_outputs.py
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
