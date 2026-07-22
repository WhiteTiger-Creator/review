#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
printf '{"version":"1.0.0","results":[]}\n' > /logs/verifier/ctrf.json

if [ "$PWD" = "/" ] || [ -z "${PWD:-}" ]; then
  echo "Error: No working directory set. Please set WORKDIR in your Dockerfile before running this script." >&2
  exit 1
fi

export PATH="/opt/verifier-venv/bin:/app/bin:/usr/local/cargo/bin:${PATH}"
MOUNT_TESTS="${TEST_DIR:-/tests}"
TEST_WORK="/tmp/fm-verifier-tests"
rm -rf "${TEST_WORK}" /opt/verifier-fixtures
mkdir -p "${TEST_WORK}" /opt/verifier-fixtures
cp -a "${MOUNT_TESTS}/." "${TEST_WORK}/"
if [ -d "${TEST_WORK}/verifier_fixtures" ]; then
  cp -a "${TEST_WORK}/verifier_fixtures/." /opt/verifier-fixtures/
  rm -rf "${TEST_WORK}/verifier_fixtures"
fi
chown -R root:root /opt/verifier-fixtures
chmod -R go-rwx /opt/verifier-fixtures

cd /app
set +e
cargo build --release --locked
BUILD_RC=$?
if [ "$BUILD_RC" -eq 0 ]; then
  mkdir -p /app/bin
  cp /app/target/release/fmctl /app/bin/fmctl
fi

/opt/verifier-venv/bin/python3 -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json \
  "${TEST_WORK}/test_outputs.py" -rA
PYTEST_RC=$?

[ "$BUILD_RC" -eq 0 ] && [ "$PYTEST_RC" -eq 0 ]
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
