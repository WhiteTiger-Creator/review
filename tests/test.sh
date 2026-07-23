#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
  exit 0
fi

TEST_DIR="${TEST_DIR:-/tests}"
cd "$TEST_DIR"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -I -m pytest -p no:cacheprovider -p ctrf -c /dev/null --confcutdir="$TEST_DIR" --rootdir="$TEST_DIR" "$TEST_DIR/test_outputs.py" -rA --ctrf /logs/verifier/ctrf.json
rc=$?
if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
