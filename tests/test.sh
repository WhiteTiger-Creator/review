#!/bin/bash

# Verifier dependencies are installed in environment/Dockerfile.

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

# Isolated Python (-I) so a planted /app/pytest.py cannot shadow the real package.
# Harness may set TEST_DIR; default keeps /tests/test_outputs.py under --confcutdir/--rootdir.
python3 -I -m pytest \
  --confcutdir="${TEST_DIR:-/tests}" \
  --rootdir="${TEST_DIR:-/tests}" \
  -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json \
  /tests/test_outputs.py -rA

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
