#!/bin/bash

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    exit 1
fi

mkdir -p /logs/verifier

# Never let a stale reward survive this run. The write below can fail (e.g. if the file
# was pre-created unwritable), and without this a previous run's value would be read as
# though it were this run's result.
rm -f /logs/verifier/reward.txt


pytest_bin=/usr/local/bin/pytest
if [ ! -x "$pytest_bin" ]; then
    echo "Error: $pytest_bin not found or not executable."
    exit 1
fi

# PYTHONNOUSERSITE is the load-bearing flag here, not PYTHONSAFEPATH. Removing the script
# directory from sys.path (PYTHONSAFEPATH) closes a local-module shadow, but the user
# site-packages directory is writable by the same account that runs the tests and is
# consulted regardless: a `pytest11` entry point, a .pth file, or a usercustomize module
# planted there all execute inside the pytest process and can force the exit status.
# PYTHONNOUSERSITE=1 closes that whole family. PYTHONPATH is cleared for the same reason,
# and -p no:cacheprovider keeps pytest from writing into the tree it is grading.
PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONPATH= "$pytest_bin" -p no:cacheprovider --confcutdir=/tests --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
code=$?
if [ "$code" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
