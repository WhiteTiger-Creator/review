#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier
if [ "${1:-}" = solve ]; then
  rm -f /app/promotion-plan.json
  /solution/solve.sh
fi
pytest -q -rA /tests/test_outputs.py
rc=$?
if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
