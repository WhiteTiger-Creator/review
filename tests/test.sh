#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
export PYTHONSAFEPATH=1
export PATH=/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin
python3 -m pytest -rA -c /dev/null --confcutdir=/tests /tests/test_outputs.py
rc=$?
if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
