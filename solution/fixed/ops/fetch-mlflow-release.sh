#!/usr/bin/env bash
set -euo pipefail

MLFLOW_RELEASE_URL="${MLFLOW_RELEASE_URL:-http://127.0.0.1:18081/releases/mlflow-2.16.2.tar.gz}"
MLFLOW_RELEASE_SHA256_FILE="${MLFLOW_RELEASE_SHA256_FILE:-/data/mlflow-release/mlflow-2.16.2.sha256}"
MLFLOW_RELEASE_CACHE="${MLFLOW_RELEASE_CACHE:-/app/.cache/mlflow-release}"

ARCHIVE_NAME="$(basename "${MLFLOW_RELEASE_URL}")"
CACHE_ARCHIVE="${MLFLOW_RELEASE_CACHE}/${ARCHIVE_NAME}"
SCHEMA_MARKER="${MLFLOW_RELEASE_CACHE}/schema.path"
SCHEMA_REL="mlflow/server/graphql/schemas/run_callback.schema.json"

mkdir -p "${MLFLOW_RELEASE_CACHE}"

origin_of() {
  python3 - "$1" <<'PY'
import sys
from urllib.parse import urlparse
u = urlparse(sys.argv[1])
port = u.port or (443 if u.scheme == "https" else 80)
print(f"{u.scheme}://{u.hostname}:{port}")
PY
}

EXPECTED_ORIGIN="$(origin_of "${MLFLOW_RELEASE_URL}")"
EXPECTED_SHA="$(awk '{print tolower($1)}' "${MLFLOW_RELEASE_SHA256_FILE}")"

if [[ ! -f "${CACHE_ARCHIVE}" ]]; then
  echo "Fetching ${MLFLOW_RELEASE_URL}"
  # Reject redirects outside configured origin by resolving Location manually.
  FINAL_URL="${MLFLOW_RELEASE_URL}"
  for _ in $(seq 1 5); do
    HEADERS="$(mktemp)"
    CODE="$(curl -sS -D "${HEADERS}" -o /dev/null -w '%{http_code}' "${FINAL_URL}" || true)"
    if [[ "${CODE}" == "301" || "${CODE}" == "302" || "${CODE}" == "303" || "${CODE}" == "307" || "${CODE}" == "308" ]]; then
      LOC="$(awk 'tolower($1)=="location:" {print $2}' "${HEADERS}" | tr -d '\r' | tail -n1)"
      rm -f "${HEADERS}"
      if [[ -z "${LOC}" ]]; then
        echo "redirect without Location" >&2
        exit 1
      fi
      if [[ "${LOC}" != http* ]]; then
        # relative redirect
        LOC="$(python3 - "${FINAL_URL}" "${LOC}" <<'PY'
import sys
from urllib.parse import urljoin
print(urljoin(sys.argv[1], sys.argv[2]))
PY
)"
      fi
      LOC_ORIGIN="$(origin_of "${LOC}")"
      if [[ "${LOC_ORIGIN}" != "${EXPECTED_ORIGIN}" ]]; then
        echo "rejecting external redirect to ${LOC}" >&2
        exit 1
      fi
      FINAL_URL="${LOC}"
      continue
    fi
    rm -f "${HEADERS}"
    break
  done
  curl -fsS --max-redirs 0 "${FINAL_URL}" -o "${CACHE_ARCHIVE}.tmp"
  mv "${CACHE_ARCHIVE}.tmp" "${CACHE_ARCHIVE}"
fi

ACTUAL_SHA="$(sha256sum "${CACHE_ARCHIVE}" | awk '{print tolower($1)}')"
if [[ "${ACTUAL_SHA}" != "${EXPECTED_SHA}" ]]; then
  echo "SHA-256 mismatch for ${CACHE_ARCHIVE}" >&2
  echo "expected=${EXPECTED_SHA} actual=${ACTUAL_SHA}" >&2
  exit 1
fi

EXTRACT_DIR="${MLFLOW_RELEASE_CACHE}/extracted/${ACTUAL_SHA}"
rm -rf "${EXTRACT_DIR}"
mkdir -p "${EXTRACT_DIR}"

# Safe extract: reject traversal
while IFS= read -r entry; do
  case "${entry}" in
    /*|*\.\./*|*\.\.) echo "refusing unsafe archive entry: ${entry}" >&2; exit 1 ;;
  esac
done < <(tar -tzf "${CACHE_ARCHIVE}")

tar -xzf "${CACHE_ARCHIVE}" -C "${EXTRACT_DIR}"

SCHEMA_PATH="${EXTRACT_DIR}/${SCHEMA_REL}"
if [[ ! -f "${SCHEMA_PATH}" ]]; then
  echo "Callback schema not found at ${SCHEMA_PATH}" >&2
  exit 1
fi

printf '%s\n' "${SCHEMA_PATH}" >"${SCHEMA_MARKER}"
echo "schema.path=${SCHEMA_PATH}"
echo "mlflow release ready under ${EXTRACT_DIR}"
