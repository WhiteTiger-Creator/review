#!/usr/bin/env bash
set -euo pipefail

MIRROR_PORT="${MIRROR_PORT:-18081}"
MIRROR_BIND="127.0.0.1"
DATA_DIR="${MLFLOW_RELEASE_DATA:-/data/mlflow-release}"
STATE_DIR="/tmp/graphrun-mirror"
PID_FILE="${STATE_DIR}/release-mirror.pid"
LOG_FILE="${STATE_DIR}/release-mirror.log"
JAR="${RELEASE_MIRROR_JAR:-/app/release-mirror/build/libs/release-mirror.jar}"

mkdir -p "${STATE_DIR}"

stop_stale() {
  if [[ -f "${PID_FILE}" ]]; then
    local pid
    pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]]; then
      kill "${pid}" 2>/dev/null || true
      for _ in $(seq 1 30); do
        kill -0 "${pid}" 2>/dev/null || break
        sleep 0.1
      done
      kill -9 "${pid}" 2>/dev/null || true
    fi
    rm -f "${PID_FILE}"
  fi
}

if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  if curl -fsS "http://${MIRROR_BIND}:${MIRROR_PORT}/health" >/dev/null 2>&1; then
    echo "Release mirror already running (pid $(cat "${PID_FILE}"))"
    echo "Release mirror ready at http://${MIRROR_BIND}:${MIRROR_PORT}"
    exit 0
  fi
  echo "Release mirror pid $(cat "${PID_FILE}") not healthy; restarting"
  stop_stale
fi

if [[ ! -f "${JAR}" ]]; then
  echo "Release mirror jar missing; building offline"
  /app/pkg/ops/build-offline.sh
fi

nohup java -jar "${JAR}" "${MIRROR_PORT}" "${DATA_DIR}" \
  >"${LOG_FILE}" 2>&1 &
echo $! >"${PID_FILE}"
echo "Started release mirror pid $(cat "${PID_FILE}")"

for _ in $(seq 1 120); do
  if curl -fsS "http://${MIRROR_BIND}:${MIRROR_PORT}/health" >/dev/null 2>&1; then
    echo "Release mirror ready at http://${MIRROR_BIND}:${MIRROR_PORT}"
    exit 0
  fi
  sleep 0.5
done

echo "Release mirror failed health check; see ${LOG_FILE}" >&2
exit 1
