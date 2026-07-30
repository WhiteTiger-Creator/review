#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    exit 1
fi

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GOMODCACHE="${GOMODCACHE:-/opt/gomodcache}"
export GOPROXY=off
export GOFLAGS=-mod=mod
export GOTOOLCHAIN=local

rm -f /tmp/dungeond
if ! (cd /app && go build -o /tmp/dungeond .); then
    echo "FATAL: go build of /app failed"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
(cd "$TESTS_DIR/dbdump" && go build -o /tmp/dbdump .) || {
    echo "FATAL: go build of the dbdump helper failed"
    echo 0 > /logs/verifier/reward.txt
    exit 1
}

pkill -f dungeond 2>/dev/null || true
fuser -k /app/data/dungeon.db 2>/dev/null || true
sleep 1

python3 -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json "$TESTS_DIR/test_outputs.py" -rA
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
