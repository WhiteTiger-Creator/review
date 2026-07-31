#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${1:-/app/pkg}"
SEED_ROOT="${SEED_ROOT:-${SCRIPT_DIR}/pkg-seed}"
COMMON_SEED="${SEED_ROOT}/common"
CANDIDATES_SEED="${SEED_ROOT}/lost-policy-candidates"

export GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-GraphRun Release Bot}"
export GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-release-bot@example.com}"
export GIT_COMMITTER_NAME="${GIT_COMMITTER_NAME:-GraphRun Release Bot}"
export GIT_COMMITTER_EMAIL="${GIT_COMMITTER_EMAIL:-release-bot@example.com}"

git_date() {
  export GIT_AUTHOR_DATE="$1"
  export GIT_COMMITTER_DATE="$1"
}

policy_emergency() {
  cat <<'EOF'
policy_version: "2025.12"
approval_required: true
attestation_schema_version: "1"
allowed_signing_keys:
  - signer-2025
  - emergency-signer
domains:
  graph: GRAPHRUN.GRAPH.v1
  run: GRAPHRUN.RUN.v1
  callback: GRAPHRUN.CALLBACK.v1
  attestation: GRAPHRUN.ATTEST.v1
signing:
  keys:
    - key_id: signer-2025
      private_key_path: /data/keys/signer-2025.pk8
      public_key_path: /data/keys/signer-2025.pub
      not_before: "2025-01-01T00:00:00Z"
      not_after: "2026-01-01T00:00:00Z"
      status: active
    - key_id: emergency-signer
      private_key_path: /data/keys/emergency-signer.pk8
      public_key_path: /data/keys/emergency-signer.pub
      not_before: "2025-12-01T00:00:00Z"
      not_after: "2026-02-01T00:00:00Z"
      status: active
EOF
}

policy_authoritative() {
  cat <<'EOF'
policy_version: "2026.1"
approval_required: true
attestation_schema_version: "1"
allowed_signing_keys:
  - signer-2025
  - signer-2026
domains:
  graph: GRAPHRUN.GRAPH.v1
  run: GRAPHRUN.RUN.v1
  callback: GRAPHRUN.CALLBACK.v1
  attestation: GRAPHRUN.ATTEST.v1
signing:
  keys:
    - key_id: signer-2025
      private_key_path: /data/keys/signer-2025.pk8
      public_key_path: /data/keys/signer-2025.pub
      not_before: "2025-01-01T00:00:00Z"
      not_after: "2026-01-01T00:00:00Z"
      status: active
    - key_id: signer-2026
      private_key_path: /data/keys/signer-2026.pk8
      public_key_path: /data/keys/signer-2026.pub
      not_before: "2026-01-01T00:00:00Z"
      not_after: "2027-01-01T00:00:00Z"
      status: active
EOF
}

policy_permissive_unauthorized() {
  cat <<'EOF'
policy_version: "2026.99"
approval_required: false
attestation_schema_version: "1"
allowed_signing_keys:
  - signer-2025
  - signer-2026
  - any-signer
domains:
  graph: GRAPHRUN.GRAPH.v1
  run: GRAPHRUN.RUN.v1
  callback: GRAPHRUN.CALLBACK.v1
  attestation: GRAPHRUN.ATTEST.v1
signing:
  keys:
    - key_id: signer-2025
      private_key_path: /data/keys/signer-2025.pk8
      public_key_path: /data/keys/signer-2025.pub
      not_before: "2025-01-01T00:00:00Z"
      not_after: "2027-01-01T00:00:00Z"
      status: active
    - key_id: signer-2026
      private_key_path: /data/keys/signer-2026.pk8
      public_key_path: /data/keys/signer-2026.pub
      not_before: "2026-01-01T00:00:00Z"
      not_after: "2027-01-01T00:00:00Z"
      status: active
    - key_id: any-signer
      private_key_path: /data/keys/any-signer.pk8
      public_key_path: /data/keys/any-signer.pub
      not_before: "2020-01-01T00:00:00Z"
      not_after: "2030-01-01T00:00:00Z"
      status: active
EOF
}

rm -rf "${DEST}"
mkdir -p "${DEST}"
cp -a "${COMMON_SEED}/." "${DEST}/"
rm -rf "${DEST}/.gradle" "${DEST}"/*/build
mkdir -p "${DEST}/config"

git -C "${DEST}" init -b main
git -C "${DEST}" config gc.auto 0
git -C "${DEST}" config gc.reflogExpire never
git -C "${DEST}" config gc.reflogExpireUnreachable never

git_date "2024-08-12T10:00:00+00:00"
git -C "${DEST}" add -A
git -C "${DEST}" commit -m "Initial GraphRunSigner import"

mkdir -p "${DEST}/config"
policy_emergency >"${DEST}/config/signing-policy.yaml"
git_date "2025-12-18T14:30:00+00:00"
git -C "${DEST}" add config/signing-policy.yaml
git -C "${DEST}" commit -m "Emergency signing policy 2025.12

Approved-By: bob@example.com
Policy-Window: 2025.12-emergency"

EMERGENCY_COMMIT="$(git -C "${DEST}" rev-parse HEAD)"

policy_authoritative >"${DEST}/config/signing-policy.yaml"
git_date "2026-01-20T09:15:00+00:00"
git -C "${DEST}" commit -am "Authoritative signing policy 2026.1

Approved-By: alice@example.com
Policy-Window: 2026.1"

AUTHORITATIVE_COMMIT="$(git -C "${DEST}" rev-parse HEAD)"

policy_permissive_unauthorized >"${DEST}/config/signing-policy.yaml"
git_date "2026-02-28T23:59:00+00:00"
git -C "${DEST}" commit -am "Permissive rollout policy draft 2026.99

Approved-By: nobody@example.com
Policy-Window: experimental"

PERMISSIVE_COMMIT="$(git -C "${DEST}" rev-parse HEAD)"

rm -f "${DEST}/config/signing-policy.yaml"
git_date "2026-03-02T08:00:00+00:00"
git -C "${DEST}" commit -am "INF-4412: remove signing-policy.yaml from deploy branch

History rewrite left policy bytes only in unreachable commits."

# Preserve dangling policy commits and reflog entries for forensic recovery.
for label in \
  "emergency-superseded:${EMERGENCY_COMMIT}" \
  "authoritative-2026.1:${AUTHORITATIVE_COMMIT}" \
  "permissive-unauthorized:${PERMISSIVE_COMMIT}"; do
  name="${label%%:*}"
  oid="${label##*:}"
  git -C "${DEST}" update-ref "refs/policy-candidates/${name}" "${oid}"
  git -C "${DEST}" update-ref -d "refs/policy-candidates/${name}"
done

MAIN_AFTER_REMOVAL="$(git -C "${DEST}" rev-parse HEAD)"

# Populate reflog with candidate checkouts, then return to the policy-less main tip.
git -C "${DEST}" checkout --detach "${EMERGENCY_COMMIT}"
git -C "${DEST}" checkout --detach "${AUTHORITATIVE_COMMIT}"
git -C "${DEST}" checkout --detach "${PERMISSIVE_COMMIT}"
git -C "${DEST}" checkout -B main "${MAIN_AFTER_REMOVAL}"

# Ensure the working tree tip still has no active policy file.
rm -f "${DEST}/config/signing-policy.yaml"
if git -C "${DEST}" cat-file -e "HEAD:config/signing-policy.yaml" 2>/dev/null; then
  echo "bootstrap invariant violated: HEAD still tracks signing-policy.yaml" >&2
  exit 1
fi

LOST_DIR="${DEST}/../lost-policy-candidates"
mkdir -p "${LOST_DIR}"
if [[ -d "${CANDIDATES_SEED}" ]]; then
  cp -a "${CANDIDATES_SEED}/." "${LOST_DIR}/"
fi

cat >"${DEST}/config/POLICY_BOOTSTRAP.md" <<'EOF'
# Policy bootstrap notes

Active `config/signing-policy.yaml` was removed during INF-4412.

Recover policy bytes from local reflogs and unreachable objects using the
GraphRunSigner operations manual roster rules (approval metadata, policy window,
and signing-key constraints). Candidate snapshots may also appear under
`../lost-policy-candidates/` for cross-checking.
EOF

git -C "${DEST}" add config/POLICY_BOOTSTRAP.md
git_date "2026-03-02T08:10:00+00:00"
if ! git -C "${DEST}" diff --cached --quiet; then
  git -C "${DEST}" commit -m "Document INF-4412 policy recovery procedure"
fi

test ! -f "${DEST}/config/signing-policy.yaml"
echo "Bootstrapped ${DEST}"
