#!/bin/bash
# Verifier entrypoint. No `set -e`: the reward must always be written, even when pytest fails.
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
if [ -d /app ]; then
    cd /app
fi
# Strip group/other access to the oracle and expected outputs. pytest runs as root and
# is unaffected; the graded candidate is dropped to an unprivileged user (see
# test_outputs.py) and so cannot read the answers from /tests instead of computing them.
chmod -R go-rwx /tests 2>/dev/null || true
/opt/verifier-venv/bin/python -I -m pytest -p no:cacheprovider /tests/test_outputs.py -rA
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
