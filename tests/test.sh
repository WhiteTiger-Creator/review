#!/bin/bash
# Verifier entry point. pytest + plugins are baked into the image at build time;
# the network is offline at run time (task.toml: allow_internet = false), so this
# script must NOT install anything or fetch from the network.
set -uo pipefail
export PYTHONDONTWRITEBYTECODE=1

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Set a WORKDIR in the Dockerfile." >&2
    mkdir -p /logs/verifier
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

mkdir -p /logs/verifier
# Fail-safe: a crash or timeout before the reward block below still grades 0.
echo 0 > /logs/verifier/reward.txt

# The image WORKDIR is /app, which the agent may write to. Everything below
# keeps the runner and its configuration off that tree: run from /tests, resolve
# pytest through the installed console script rather than `python3 -m pytest`
# (only the module form puts the working directory on sys.path), pin the ini and
# the rootdir, and stop conftest discovery at /tests.
cd /tests || exit 0
export PYTHONSAFEPATH=1
export PYTHONNOUSERSITE=1
unset PYTHONPATH PYTHONSTARTUP PYTHONINSPECT

/usr/local/bin/pytest \
    -p no:cacheprovider \
    -c /tests/pytest.ini \
    -o addopts= \
    --rootdir=/tests \
    --confcutdir=/tests \
    --ctrf /logs/verifier/ctrf.json \
    /tests/test_outputs.py -rA
# Canonical reward block below. Keep NOTHING (not even comments) between
# `rc=$?` and its `if`. The platform's static check requires them adjacent
# (a blank line is fine, a comment line is not). Do NOT add a trailing `exit`
# after `fi` either (check_test_sh will fail CI). Harbor reads reward.txt, not
# the script exit code.
rc=$?

if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
