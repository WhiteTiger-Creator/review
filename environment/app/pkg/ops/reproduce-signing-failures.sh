#!/usr/bin/env bash
set -euo pipefail

SIGNER_URL="${SIGNER_URL:-http://127.0.0.1:18082}"
RUN_ROOT="${GRAPHRUN_RUN_ROOT:-/data/runs}"
POLICY_PATH="${GRAPHRUN_POLICY:-/app/pkg/config/signing-policy.yaml}"
CACHE_ROOT="${MLFLOW_RELEASE_CACHE:-/app/.cache/mlflow-release}"

issues=0
report() {
  echo "MISMATCH: $*"
  issues=$((issues + 1))
}

echo "=== GraphRunSigner visible failure reproduction ==="

# 1. Equivalent graphs should canonicalize to the same digest.
if [[ -f "${RUN_ROOT}/visible-run-a/graph.json" && -f "${RUN_ROOT}/visible-run-b/graph.json" ]]; then
  digest_a="$(python3 - <<'PY' "${RUN_ROOT}/visible-run-a/graph.json"
import hashlib, json, sys
from pathlib import Path
# Fixture byte hash for visible mismatch reporting (not the contract digest).
data = Path(sys.argv[1]).read_bytes()
print(hashlib.sha256(data).hexdigest())
PY
)"
  digest_b="$(python3 - <<'PY' "${RUN_ROOT}/visible-run-b/graph.json"
import hashlib, sys
from pathlib import Path
data = Path(sys.argv[1]).read_bytes()
print(hashlib.sha256(data).hexdigest())
PY
)"
  if [[ "${digest_a}" != "${digest_b}" ]]; then
    report "equivalent graph fixtures produce different naive digests (${digest_a} vs ${digest_b})"
  else
    echo "OK: graph fixture byte digests match (service may still disagree after canonicalization)"
  fi
else
  report "visible graph fixtures missing under ${RUN_ROOT}"
fi

# 2. Missing active signing policy in working tree.
if [[ ! -f "${POLICY_PATH}" ]]; then
  report "config/signing-policy.yaml absent from working tree (policy recovery required)"
else
  echo "NOTE: signing-policy.yaml present at ${POLICY_PATH}"
fi

# 3. Cached MLflow tarball trust — starter fetch script skips re-verification.
tampered="${CACHE_ROOT}/tampered/mlflow-2.16.2.tar.gz"
if [[ -f "${tampered}" ]]; then
  report "tampered cache sample present at ${tampered}; fetch-mlflow-release.sh may reuse without SHA-256 check"
fi
if [[ -f "${CACHE_ROOT}/mlflow-2.16.2.tar.gz" ]]; then
  report "release cache populated; starter fetch path skips digest verification on cache hit"
fi

# 4. Redirect / origin enforcement (mirror endpoints exist for manual probing).
mirror="${MLFLOW_RELEASE_URL:-http://127.0.0.1:18081}"
if curl -fsS "${mirror}/redirect-external" -o /dev/null 2>/dev/null; then
  report "mirror exposes redirect-external; starter fetch follows redirects without origin pinning"
fi

# 5. Callback replay / identity probes against live API when available.
if curl -fsS "${SIGNER_URL}/health" >/dev/null 2>&1; then
  replay_body='{"event_id":"replay-probe","run_id":"visible-run-a","experiment_id":"exp-visible-a","graph_digest":"0000000000000000000000000000000000000000000000000000000000000000","policy_version":"2026.1","schema_version":"1","status":"RUNNING","occurred_at":"2026-01-10T12:00:00Z","metrics":{}}'
  code1="$(curl -s -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d "${replay_body}" "${SIGNER_URL}/v1/callbacks" || true)"
  code2="$(curl -s -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d "${replay_body}" "${SIGNER_URL}/v1/callbacks" || true)"
  if [[ "${code1}" == "200" && "${code2}" == "200" ]]; then
    echo "NOTE: duplicate callback accepted with HTTP 200 (idempotence behavior depends on implementation)"
  else
    report "callback probe returned ${code1}/${code2} (expected stable idempotent handling for identical replay)"
  fi

  conflict_body='{"event_id":"replay-probe","run_id":"visible-run-a","experiment_id":"exp-visible-a","graph_digest":"0000000000000000000000000000000000000000000000000000000000000000","policy_version":"2026.1","schema_version":"1","status":"FAILED","occurred_at":"2026-01-10T12:01:00Z","metrics":{},"artifact_digest":"1111111111111111111111111111111111111111111111111111111111111111"}'
  code_conflict="$(curl -s -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d "${conflict_body}" "${SIGNER_URL}/v1/callbacks" || true)"
  if [[ "${code_conflict}" != "409" ]]; then
    report "conflicting replay returned HTTP ${code_conflict} (expected 409 replay_conflict)"
  fi
else
  report "GraphRunSigner not reachable at ${SIGNER_URL} (start via start-pkg.sh)"
fi

echo "=== Summary: ${issues} mismatch(es) recorded ==="
if [[ "${issues}" -gt 0 ]]; then
  exit 1
fi
exit 0
