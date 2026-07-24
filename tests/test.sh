#!/bin/bash
# All test dependencies are pre-installed in the image (pytest in /opt/venv).
# Every check runs the compiled /app/audit executable against release-ledger
# files generated at test time and never touches the network, so the verifier
# always
# completes offline. No package installation happens here.
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Set a WORKDIR in the Dockerfile." >&2
    exit 1
fi

unset PYTEST_ADDOPTS

cd /tests
PYTHONSAFEPATH=1 /opt/venv/bin/pytest -c /tests/pytest.ini -o cache_dir=/tmp/pytest_cache test_outputs.py -rA --ctrf /logs/verifier/ctrf.json --rootdir=/tests --confcutdir=/tests
pytest_rc=$?

# Gate on the parsed CTRF counts, not the bare pytest exit code: a collect-only
# ancestor config would let pytest exit 0 having run zero tests, so require a
# genuine run (total > 0, all passed) before granting reward. check_reward.py
# folds the pytest exit code and the CTRF counts into a single exit status so the
# reward section below stays in the required canonical form.
/opt/venv/bin/python3 /tests/check_reward.py "$pytest_rc"
result=$?
if [ "$result" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
