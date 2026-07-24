#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
export PYTHONDONTWRITEBYTECODE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PYTEST_ADDOPTS=
export TMPDIR=/tmp
export TASK_RUN_UID=10001

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in the Dockerfile."
    exit 0
fi

chown "$TASK_RUN_UID:$TASK_RUN_UID" /app/task_file /app/task_file/src /app/task_file/src/Program.cs /app/task_file/Makefile

setpriv --reuid="$TASK_RUN_UID" --regid="$TASK_RUN_UID" --clear-groups \
    make -C /app/task_file sphere-flux >/tmp/sphere-flux-build.log 2>&1
build_rc=$?
if [ "$build_rc" -ne 0 ]; then
    cat /tmp/sphere-flux-build.log
    exit 0
fi

cd /tmp || exit 0
printf '[pytest]\n' > /tmp/sphere-flux-pytest.ini
PYTHONSAFEPATH=1 /usr/bin/python3 -m pytest \
    -c /tmp/sphere-flux-pytest.ini \
    --rootdir=/tests \
    --confcutdir=/tests \
    --import-mode=importlib \
    -p no:cacheprovider \
    /tests/test_outputs.py \
    -rA
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
