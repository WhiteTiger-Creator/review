#!/bin/sh
mkdir -p /logs/verifier
printf '%s\n' '{"reportFormat":"CTRF","specVersion":"0.0.0","generatedBy":"preflight","results":{"tool":{"name":"preflight"},"summary":{"tests":1,"passed":0,"failed":1,"skipped":0,"pending":0,"other":0,"start":0,"stop":0},"tests":[{"name":"verifier_did_not_complete","status":"failed","duration":0}]}}' > /logs/verifier/ctrf.json
echo 0 > /logs/verifier/reward.txt
test_dir="${TEST_DIR:-/tests}"
candidate=/tmp/artist_country_classifier
rm -f "$candidate"
/usr/local/cargo/bin/rustc --edition=2021 -C opt-level=2 /app/analysis.rs -o "$candidate"
chmod 755 "$candidate" 2>/dev/null
chmod 700 "$test_dir"
CANDIDATE_PATH="$candidate" /opt/verifier-venv/bin/python -m pytest -q -rA --ctrf /logs/verifier/ctrf.json -p no:cacheprovider -o addopts="" "$test_dir/test_outputs.py"
status=$?
if [ "$status" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
