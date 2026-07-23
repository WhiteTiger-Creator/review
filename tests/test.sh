#!/usr/bin/env bash

mkdir -p /logs/verifier
pytest -q -rA -p no:cacheprovider /tests/test_outputs.py
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
