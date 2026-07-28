#!/bin/sh
mkdir -p /logs/verifier
printf '%s\n' '{"reportFormat":"CTRF","specVersion":"0.0.0","generatedBy":"preflight","results":{"tool":{"name":"preflight"},"summary":{"tests":1,"passed":0,"failed":1,"skipped":0,"pending":0,"other":0,"start":0,"stop":0},"tests":[{"name":"verifier_did_not_complete","status":"failed","duration":0}]}}' > /logs/verifier/ctrf.json
echo 0 > /logs/verifier/reward.txt
test_dir="${TEST_DIR:-/tests}"
candidate=/tmp/artist_country_classifier
rm -f "$candidate"
chmod 700 "$test_dir"
/usr/bin/setpriv --reuid=candidate --regid=candidate --clear-groups /usr/bin/env -i HOME=/home/candidate TMPDIR=/tmp CARGO_HOME=/usr/local/cargo RUSTUP_HOME=/usr/local/rustup PATH=/usr/local/cargo/bin:/usr/local/bin:/usr/bin:/bin /bin/sh -ec 'test ! -r "$1/fixtures/targets.csv"; /usr/local/cargo/bin/rustc --edition=2021 -C opt-level=2 /app/analysis.rs -o "$2"' sh "$test_dir" "$candidate"
chmod 755 "$candidate" 2>/dev/null
cd /root
CANDIDATE_PATH="$candidate" PYTHONSAFEPATH=1 PYTHONNOUSERSITE=1 PYTHONPATH= PYTHONHOME= /opt/verifier-venv/bin/python -m pytest -q -rA --ctrf /logs/verifier/ctrf.json -p no:cacheprovider -o addopts="" "$test_dir/test_outputs.py"
status=$?
if [ "$status" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
