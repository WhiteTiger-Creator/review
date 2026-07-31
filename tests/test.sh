#!/bin/bash

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    exit 1
fi

mkdir -p /logs/verifie

# Normalize CRLF if the harness mounts Windows-authored scripts.
for f in /tests/test.sh /tests/test_outputs.py; do
  [ -f "$f" ] || continue
  tr -d '\r' < "$f" > /tmp/tb_norm && cat /tmp/tb_norm > "$f"
done

PYTHON_BIN="/opt/verifier/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" -m pytest -o cache_dir=/tmp/pytest_cache --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA

rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
