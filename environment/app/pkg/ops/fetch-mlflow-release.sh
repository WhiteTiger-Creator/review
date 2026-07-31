#!/usr/bin/env bash
set -euo pipefail

MLFLOW_RELEASE_URL="${MLFLOW_RELEASE_URL:-http://127.0.0.1:18081/releases/mlflow-2.16.2.tar.gz}"
MLFLOW_RELEASE_SHA256_FILE="${MLFLOW_RELEASE_SHA256_FILE:-/data/mlflow-release/mlflow-2.16.2.sha256}"
MLFLOW_RELEASE_CACHE="${MLFLOW_RELEASE_CACHE:-/app/.cache/mlflow-release}"

ARCHIVE_NAME="$(basename "${MLFLOW_RELEASE_URL}")"
CACHE_ARCHIVE="${MLFLOW_RELEASE_CACHE}/${ARCHIVE_NAME}"
EXTRACT_DIR="${MLFLOW_RELEASE_CACHE}/extracted"
SCHEMA_MARKER="${MLFLOW_RELEASE_CACHE}/schema.path"
SCHEMA_REL="mlflow/server/graphql/schemas/run_callback.schema.json"

mkdir -p "${MLFLOW_RELEASE_CACHE}"

read_expected_digest() {
  awk '{print tolower($1)}' "${MLFLOW_RELEASE_SHA256_FILE}"
}

EXPECTED_SHA="$(read_expected_digest)"
VERIFIED_MARKER="${MLFLOW_RELEASE_CACHE}/.verified-${EXPECTED_SHA}"

cache_digest() {
  sha256sum "${CACHE_ARCHIVE}" | awk '{print tolower($1)}'
}

# Warm-path reuse: hash the archive for the log line, then honor schema.path / .verified-*.
if [[ -f "${CACHE_ARCHIVE}" && -f "${VERIFIED_MARKER}" ]]; then
  ACTUAL_SHA="$(cache_digest)"
  echo "cache digest ${ACTUAL_SHA} expected ${EXPECTED_SHA}"
  if [[ -f "${SCHEMA_MARKER}" ]]; then
    PREV_SCHEMA="$(tr -d '\r\n' < "${SCHEMA_MARKER}")"
    if [[ -n "${PREV_SCHEMA}" && -f "${PREV_SCHEMA}" ]]; then
      echo "Reusing cache ${CACHE_ARCHIVE}"
      echo "schema.path=${PREV_SCHEMA}"
      echo "mlflow release ready under $(dirname "${PREV_SCHEMA}")"
      exit 0
    fi
  fi
fi

if [[ -f "${CACHE_ARCHIVE}" && -f "${SCHEMA_MARKER}" ]]; then
  ACTUAL_SHA="$(cache_digest)"
  echo "cache digest ${ACTUAL_SHA} expected ${EXPECTED_SHA}"
  PREV_SCHEMA="$(tr -d '\r\n' < "${SCHEMA_MARKER}")"
  if [[ -n "${PREV_SCHEMA}" && -f "${PREV_SCHEMA}" ]]; then
    echo "Reusing cache ${CACHE_ARCHIVE}"
    echo "schema.path=${PREV_SCHEMA}"
    echo "mlflow release ready under $(dirname "${PREV_SCHEMA}")"
    exit 0
  fi
fi

if [[ -f "${CACHE_ARCHIVE}" ]]; then
  ACTUAL_SHA="$(cache_digest)"
  if [[ "${ACTUAL_SHA}" != "${EXPECTED_SHA}" ]]; then
    echo "SHA-256 mismatch for ${CACHE_ARCHIVE}" >&2
    rm -f "${CACHE_ARCHIVE}" "${VERIFIED_MARKER}"
    rm -rf "${EXTRACT_DIR}"
  else
    TARBALL="${CACHE_ARCHIVE}"
  fi
fi

if [[ -z "${TARBALL:-}" ]]; then
  echo "Fetching ${MLFLOW_RELEASE_URL}"
  curl -fsSL "${MLFLOW_RELEASE_URL}" -o "${CACHE_ARCHIVE}.tmp"
  mv "${CACHE_ARCHIVE}.tmp" "${CACHE_ARCHIVE}"
  ACTUAL_SHA="$(cache_digest)"
  if [[ "${ACTUAL_SHA}" != "${EXPECTED_SHA}" ]]; then
    echo "SHA-256 mismatch for ${CACHE_ARCHIVE}" >&2
    exit 1
  fi
  TARBALL="${CACHE_ARCHIVE}"
fi

rm -rf "${EXTRACT_DIR}"
mkdir -p "${EXTRACT_DIR}"
tar -xzf "${TARBALL}" -C "${EXTRACT_DIR}"

SCHEMA_PATH="${EXTRACT_DIR}/${SCHEMA_REL}"
if [[ ! -f "${SCHEMA_PATH}" ]]; then
  echo "Callback schema not found at ${SCHEMA_PATH}" >&2
  exit 1
fi

printf '%s\n' "${SCHEMA_PATH}" >"${SCHEMA_MARKER}"
: >"${VERIFIED_MARKER}"
echo "schema.path=${SCHEMA_PATH}"
echo "mlflow release ready under ${EXTRACT_DIR}"
