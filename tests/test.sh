#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

export HOME=/tmp
export GOCACHE=/tmp/go-build
export GOPATH=/tmp/go
export XDG_CACHE_HOME=/tmp/.cache
export PYTHONDONTWRITEBYTECODE=1
export GOTOOLCHAIN=local
export GOFLAGS=-mod=mod
export PATH="/usr/local/go/bin:/opt/verifier-venv/bin:${PATH}"

/opt/verifier-venv/bin/python -m pytest \
    --ctrf /logs/verifier/ctrf.json \
    --rootdir=/tests \
    --import-mode=importlib \
    -p no:cacheprovider \
    -rA \
    /tests/test_outputs.py
rc=$?

if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
