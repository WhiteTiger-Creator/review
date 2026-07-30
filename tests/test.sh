#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

set -uo pipefail

if [ "$PWD" = "/" ]; then
  echo "refusing to run from /" >&2
  echo 0 > /logs/verifier/reward.txt
  exit 1
fi

TEST_DIR="${TEST_DIR:-/tests}"

# The engine is started straight from its typescript source, so confirm it still parses
# before any case runs. A source the runtime cannot strip fails closed here rather than as a
# heap of confusing case failures.
cd /app || exit 1
node --experimental-strip-types --check /app/src/topple.ts \
 && node --experimental-strip-types --check /app/src/main.ts || {
  echo 0 > /logs/verifier/reward.txt
  echo "engine source did not parse"
  exit 1
}

export PYTHONSAFEPATH=1
python3 -m pytest --confcutdir="${TEST_DIR}" --ctrf /logs/verifier/ctrf.json "${TEST_DIR}/test_outputs.py" -rA -p no:cacheprovider

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
