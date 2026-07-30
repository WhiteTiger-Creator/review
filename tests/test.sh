#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier

export PATH="/srv/mirrorveil/bin:/opt/verifier_venv/bin:${PATH}"

pytest -rA /tests/test_outputs.py
status=$?
if [ "$status" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
