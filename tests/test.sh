#!/bin/bash

# Verifier dependencies are installed in environment/Dockerfile.
# Add task-specific verifier-only Python packages there, not here.

cd /app || exit 1
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
printf '{"results":{"tests":[]}}' > /logs/verifier/ctrf.json

# Run tests
export PYTHONPATH=/tests
python3 -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
RC=$?

if [ "$RC" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
