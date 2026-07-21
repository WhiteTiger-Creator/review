#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in the Dockerfile before running this script." >&2
    exit 1
fi

/usr/local/bin/ensure-crop-server.sh || {
  echo "crop scoring server is not reachable on http://127.0.0.1:8780" >&2
  exit 1
}

set +e
python3 -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
