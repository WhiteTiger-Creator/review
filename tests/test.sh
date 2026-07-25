#!/bin/bash
mkdir -p /logs/verifier
export PYTHONSAFEPATH=1
python3 -m pytest /tests/test_outputs.py -rA -q --tb=short
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
