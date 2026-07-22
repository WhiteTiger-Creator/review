#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier

if [ "$PWD" = "/" ]; then
  echo "ERROR: verifier requires a configured working directory" >&2
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi

python -m pytest \
  -o cache_dir=/tmp/sleep-apnea-hmm-triage-pytest-cache \
  --ctrf /logs/verifier/ctrf.json \
  /tests/test_outputs.py \
  -rA
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
