#!/bin/bash
mkdir -p /logs/verifier /tmp/avila_outputs
cp /tests/ctrf_fallback.json /logs/verifier/ctrf.json
echo 0 > /logs/verifier/reward.txt
chmod 777 /tmp/avila_outputs
chmod 700 /tests
cd /tests
python3 -m pytest -p no:cacheprovider --confcutdir=/tests \
    --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
pytest_status=$?
if [ "$pytest_status" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
