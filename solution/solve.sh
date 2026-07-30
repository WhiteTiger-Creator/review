#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app

patch -p1 --forward < "${ROOT_DIR}/patches/token-exposure-fixes.patch"

opa check /app/opalib
export PATH="/usr/local/go/bin:${PATH}"
rm -rf /tmp/go-build /app/build
mkdir -p /tmp/go-build /app/build
export GOCACHE=/tmp/go-build
bash /app/scripts/build_binary.sh

bash /app/test-visible/policy-smoke.sh
bash /app/test-visible/corpus-smoke.sh
bash /app/test-visible/graph-smoke.sh
bash /app/test-visible/legacy-smoke.sh
bash /app/test-visible/recovery-smoke.sh

run_dir=/tmp/oracle-exposure
rm -rf "${run_dir}" /output/*
mkdir -p "${run_dir}" /output
cp -a /app/data/events "${run_dir}/events"
cp -a /app/config "${run_dir}/config"
cp /app/data/state/analysis-state.json "${run_dir}/analysis-state.json"

/app/bin/token-exposure-analyze \
  --events "${run_dir}/events" \
  --config "${run_dir}/config" \
  --regolib /app/opalib \
  --state "${run_dir}/analysis-state.json" \
  --output /output

/app/bin/inspect-exposure-output \
  --report /output/token_exposure_report.json \
  --dot /output/token_exposure_graph.dot

dot -Tsvg /output/token_exposure_graph.dot -o "${run_dir}/graph.svg"
python3 -m jsonschema -i /output/token_exposure_report.json /app/schemas/exposure-report.schema.json

sha256sum /output/token_exposure_report.json /output/token_exposure_graph.dot > "${run_dir}/first.sha256"

/app/bin/token-exposure-analyze \
  --events "${run_dir}/events" \
  --config "${run_dir}/config" \
  --regolib /app/opalib \
  --state "${run_dir}/analysis-state.json" \
  --output /output

sha256sum /output/token_exposure_report.json /output/token_exposure_graph.dot > "${run_dir}/second.sha256"
cmp "${run_dir}/first.sha256" "${run_dir}/second.sha256"

test -s /output/token_exposure_report.json
test -s /output/token_exposure_graph.dot
echo "oracle solve complete"
