#!/bin/bash
# Verifier entrypoint. Dependencies are installed in environment/Dockerfile.
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
exit 1
fi

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p /opt/verifier-fixtures
cp -a "${TEST_DIR}/verifier-fixtures/." /opt/verifier-fixtures/
cd /app && make all

set +e
TB3_SLATE_FIXTURES=/opt/verifier-fixtures python -m pytest \
    -o cache_dir=/tmp/pytest_cache \
    --ctrf /logs/verifier/ctrf.json \
    /tests/test_outputs.py -rA
rc=$?
if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
