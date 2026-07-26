#!/bin/bash

# Verifier dependencies are installed in environment/Dockerfile.

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
printf '%s\n' '{"results":{"tool":{"name":"ctrf-stub"},"summary":{"tests":0,"passed":0,"failed":0,"skipped":0},"tests":[]}}' > /logs/verifier/ctrf.json

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

cd /tests && PYTHONSAFEPATH=1 python -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA

python -c 'import json,sys; from pathlib import Path; d=json.loads(Path("/logs/verifier/ctrf.json").read_text()); s=(d.get("results") or {}).get("summary") or d.get("summary") or {}; p=int(s.get("passed") or 0); f=int(s.get("failed") or 0); sys.exit(0 if p>=29 and f==0 else 1)'

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
