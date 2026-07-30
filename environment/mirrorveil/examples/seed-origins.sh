#!/bin/bash
set -euo pipefail

ROOT=/srv/mirrorveil
PRIMARY="${ROOT}/origins/primary"
SECONDARY="${ROOT}/origins/secondary"
HOSTS=(releases.aurora.invalid releases.basalt.invalid)

write_tree() {
  local base="$1"
  local host="$2"
  local tag="$3"
  local d="${base}/${host}"
  mkdir -p \
    "${d}/artifacts/stable" \
    "${d}/artifacts/candidate" \
    "${d}/metadata" \
    "${d}/large" \
    "${d}/policy"

  printf 'stable-toolkit:%s:%s\n' "${host}" "${tag}" > "${d}/artifacts/stable/toolkit.tar"
  printf 'candidate-toolkit:%s:%s\n' "${host}" "${tag}" > "${d}/artifacts/candidate/toolkit.tar"
  printf '{"host":"%s","channel":"%s","kind":"metadata"}\n' "${host}" "${tag}" > "${d}/metadata/index.json"

  printf 'cookie-body:%s\n' "${host}" > "${d}/policy/set-cookie.bin"
  printf 'private-body:%s\n' "${host}" > "${d}/policy/private.bin"
  printf 'nostore-body:%s\n' "${host}" > "${d}/policy/no-store.bin"
  printf 'vary-star-body:%s\n' "${host}" > "${d}/policy/vary-star.bin"
  printf 'vary-lang-body:%s\n' "${host}" > "${d}/policy/vary-language.bin"
  printf 'vary-enc-body:%s\n' "${host}" > "${d}/policy/vary-encoding.bin"
}

for host in "${HOSTS[@]}"; do
  # Identical bytes across origins for the same host; host tag differs between hosts.
  write_tree "${PRIMARY}" "${host}" "fixture"
  write_tree "${SECONDARY}" "${host}" "fixture"
done

# Distinct host payloads so cross-host leakage is observable.
printf 'aurora-stable-unique-bytes\n' > "${PRIMARY}/releases.aurora.invalid/artifacts/stable/toolkit.tar"
cp "${PRIMARY}/releases.aurora.invalid/artifacts/stable/toolkit.tar" \
  "${SECONDARY}/releases.aurora.invalid/artifacts/stable/toolkit.tar"
printf 'basalt-stable-unique-bytes\n' > "${PRIMARY}/releases.basalt.invalid/artifacts/stable/toolkit.tar"
cp "${PRIMARY}/releases.basalt.invalid/artifacts/stable/toolkit.tar" \
  "${SECONDARY}/releases.basalt.invalid/artifacts/stable/toolkit.tar"

printf 'aurora-candidate-unique-bytes\n' > "${PRIMARY}/releases.aurora.invalid/artifacts/candidate/toolkit.tar"
cp "${PRIMARY}/releases.aurora.invalid/artifacts/candidate/toolkit.tar" \
  "${SECONDARY}/releases.aurora.invalid/artifacts/candidate/toolkit.tar"
printf 'basalt-candidate-unique-bytes\n' > "${PRIMARY}/releases.basalt.invalid/artifacts/candidate/toolkit.tar"
cp "${PRIMARY}/releases.basalt.invalid/artifacts/candidate/toolkit.tar" \
  "${SECONDARY}/releases.basalt.invalid/artifacts/candidate/toolkit.tar"

printf '{"host":"releases.aurora.invalid","id":"aurora-meta"}\n' > "${PRIMARY}/releases.aurora.invalid/metadata/index.json"
cp "${PRIMARY}/releases.aurora.invalid/metadata/index.json" \
  "${SECONDARY}/releases.aurora.invalid/metadata/index.json"
printf '{"host":"releases.basalt.invalid","id":"basalt-meta"}\n' > "${PRIMARY}/releases.basalt.invalid/metadata/index.json"
cp "${PRIMARY}/releases.basalt.invalid/metadata/index.json" \
  "${SECONDARY}/releases.basalt.invalid/metadata/index.json"

echo "seeded origin trees under ${PRIMARY} and ${SECONDARY}"
