#!/bin/bash
cd /app || exit 1
cargo build --release --offline
status=$?
if [ $status -ne 0 ]; then
  echo "build failed"
  exit $status
fi
./target/release/fpexp < data/sample-logb.in
