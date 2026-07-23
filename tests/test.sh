#!/bin/bash
# Verifier dependencies are installed in environment/Dockerfile.
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set."
  exit 1
fi
VERIFIER_DIR="$(mktemp -d /tmp/plume-verifier.XXXXXX)"
trap 'chmod 755 /tests 2>/dev/null || true; rm -rf "$VERIFIER_DIR"' EXIT
if ! cp /tests/test_outputs.py "$VERIFIER_DIR/test_outputs.py" || ! chmod 000 /tests || ! chmod 700 "$VERIFIER_DIR"; then
  echo "Error: Could not isolate verifier files."
  exit 1
fi
cd "$VERIFIER_DIR"
PYTHONNOUSERSITE=1 PYTHONPATH= python -m pytest -o cache_dir=/tmp/pytest_cache --ctrf /logs/verifier/ctrf.json "$VERIFIER_DIR/test_outputs.py" -rA

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
