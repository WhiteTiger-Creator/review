#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
# Run from the root-owned /tests dir (never the agent-writable /app) and via the
# root-owned venv interpreter, with PYTHONSAFEPATH keeping the cwd off sys.path
# and rootdir/confcutdir pinned to /tests. A file the agent plants under /app
# thus cannot shadow the interpreter, the pytest module, or a conftest.
cd /tests || { echo 0 > /logs/verifier/reward.txt; exit 1; }
PYTHONSAFEPATH=1 /opt/venv/bin/python -m pytest -rA \
  --rootdir=/tests --confcutdir=/tests -p no:cacheprovider \
  /tests/test_outputs.py
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
