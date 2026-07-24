#!/bin/bash

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    exit 1
fi

mkdir -p /logs/verifier

# pytest + pytest-json-ctrf are pre-installed in the image that runs the verifier
# (shared mode; see environment/Dockerfile). The verifier never resolves wheels at run
# time, so pytest is invoked directly.
python -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
code=$?
if [ "$code" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
