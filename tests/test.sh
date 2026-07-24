#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set."
  exit 1
fi

export PYTHONDONTWRITEBYTECODE=1

cd /tests
timeout 1100 /opt/venv/bin/python -I -P -m pytest \
  --rootdir=/tests --confcutdir=/tests \
  --ctrf /logs/verifier/ctrf.json \
  -o cache_dir=/tmp/pixilock-pytest-cache \
  test_outputs.py -rA
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
