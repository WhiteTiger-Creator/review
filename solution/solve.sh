#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app

applied=0
if [[ -s "${ROOT_DIR}/patches/harborseal-fixes.patch" ]] && command -v patch >/dev/null 2>&1; then
  if patch -p1 --batch --forward < "${ROOT_DIR}/patches/harborseal-fixes.patch"; then
    applied=1
  fi
fi
if [[ "${applied}" -eq 0 ]]; then
  cp -a "${ROOT_DIR}/fixed/lib/." /app/lib/
fi

bash /app/scripts/check-source-integrity.sh
bash /app/test-visible/library_smoke.sh
bash /app/test-visible/default_profile_smoke.sh
bash /app/test-visible/fips_profile_smoke.sh
bash /app/test-visible/mount_smoke.sh
bash /app/test-visible/legacy_compat_smoke.sh

run_dir=/tmp/harborseal-oracle
rm -rf "${run_dir}" /output/*
mkdir -p "${run_dir}" /output

/app/bin/harborseal-driver \
  --report-index /app/data/report/decision-index.json \
  --report /app/data/report/migration-report.md \
  --oci-root /app/data/oci \
  --cert-root /app/data/certs \
  --provider-root /app/data/providers \
  --state "${run_dir}/state.json" \
  --output /output

bash /app/scripts/validate-all-profiles.sh /output/profiles
python3 -m json.tool /output/setup-manifest.json >/dev/null

sha256sum /output/profiles/*.cnf /output/setup-manifest.json > "${run_dir}/first.sha256"

/app/bin/harborseal-driver \
  --report-index /app/data/report/decision-index.json \
  --report /app/data/report/migration-report.md \
  --oci-root /app/data/oci \
  --cert-root /app/data/certs \
  --provider-root /app/data/providers \
  --state "${run_dir}/state.json" \
  --output /output

sha256sum /output/profiles/*.cnf /output/setup-manifest.json > "${run_dir}/second.sha256"
cmp "${run_dir}/first.sha256" "${run_dir}/second.sha256"

test -s /output/setup-manifest.json
echo "oracle solve complete"
