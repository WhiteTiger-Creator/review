#!/bin/bash
# Verifier entrypoint. The real policy lives inside the test module (in /tests,
# never visible to the agent); this runs the behavioral tests and writes the
# reward. No Go build is needed -- the verifier is pure Python.
set -uo pipefail

# Unconditional and first: even if the WORKDIR guard below trips, a reward of 0
# is already on record instead of no reward file existing at all.
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set."
  exit 1
fi

# Run from /tests (not agent-writable) with -P (PYTHONSAFEPATH) so neither the
# cwd nor the script directory is prepended to sys.path. Without both, an
# agent-planted /app/pytest.py would shadow the real pytest package under
# `python3 -m pytest` invoked from the agent-owned /app, and a module that
# exits 0 on import would forge a pass without running a single test.
cd /tests
python3 -P -m pytest --ctrf /logs/verifier/ctrf.json test_outputs.py -rA
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
