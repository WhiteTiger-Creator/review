#!/bin/bash

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

_on_exit() {
  if [ -n "${SERVER_PID:-}" ]; then
    kill "$SERVER_PID" 2>/dev/null || true
  fi
  if [ ! -f /logs/verifier/ctrf.json ]; then
    echo '{"results":{"summary":{"tests":0,"passed":0,"failed":0,"skipped":0,"pending":0,"other":0},"tests":[]}}' \
      > /logs/verifier/ctrf.json
  fi
}
trap _on_exit EXIT

# Clear any database left from a previous run so seed data is fresh
rm -f /opt/jobqueue/jobs.db /opt/jobqueue/jobs.db-wal /opt/jobqueue/jobs.db-shm

# Rebuild the binary from whatever source the agent left
cd /app && CGO_ENABLED=1 go build -mod=vendor -o jobqueue . 2>&1

# Start server
/app/jobqueue &
SERVER_PID=$!

# Wait for server to accept connections (up to 30 s)
for i in $(seq 1 30); do
  curl -sf http://localhost:8080/stats > /dev/null 2>&1 && break
  sleep 1
done

pytest /tests/test_outputs.py -v -rA --tb=short --ctrf /logs/verifier/ctrf.json

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
