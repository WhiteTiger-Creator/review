#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
  echo "Error: WORKDIR not configured"
  exit 1
fi

# Remove any agent-accessible copy of hidden data
rm -f /app/input/collections_hidden.json /app/collections_hidden.json

# Lock down verifier sources so only root can read them
chown root:root /tests/collections_hidden.json /tests/test_outputs.py 2>/dev/null || true
chmod 600 /tests/collections_hidden.json /tests/test_outputs.py 2>/dev/null || true

# Hand /app and /logs to the unprivileged user
chown -R appuser:appuser /app /logs 2>/dev/null || true

# Build and run the candidate binary as appuser (cannot read /tests/)
su appuser -c "cd /app && go build -o /app/waterfall . 2>/dev/null && /app/waterfall" || true

# Pytest runs as root so it can read /tests/test_outputs.py and hidden fixtures
python3 -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
