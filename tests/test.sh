#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PYTHONDONTWRITEBYTECODE=1
unset PYTHONHOME PYTHONPATH PYTEST_ADDOPTS PYTEST_PLUGINS

restore_permissions() {
    chmod 0755 /tests 2>/dev/null || true
    chmod 0644 /tests/test_outputs.py 2>/dev/null || true
}
trap restore_permissions EXIT
chmod 0700 /tests
chmod 0600 /tests/test_outputs.py

# Check if we're in a valid working directory
if [ "$PWD" = "/" ]; then
    echo "The task image must set a working directory." >&2
    exit 0
fi

cd /tests || exit 0
/opt/verifier-venv/bin/python -m pytest -p ctrf.main \
    --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA --tb=short
rc=$?

if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
