#!/bin/bash

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    exit 1
fi

mkdir -p /logs/verifier
mkdir -p /opt/verifier-fixtures
TEST_DIR=/tests
cp -a "${TEST_DIR}/verifier-fixtures/." /opt/verifier-fixtures/
cd /app
cargo build --release -p undercroft_fairness
cp /app/target/release/undercroft_fairness /app/bin/undercroft-fairness
chmod +x /app/bin/undercroft-fairness

pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
