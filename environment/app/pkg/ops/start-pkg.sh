#!/usr/bin/env bash
set -euo pipefail

SIGNER_BIND="127.0.0.1"
SIGNER_PORT="${SIGNER_PORT:-18082}"
STATE_DIR="/tmp/graphrun-signer"
PID_FILE="${STATE_DIR}/graph-run-signer.pid"
LOG_FILE="${STATE_DIR}/graph-run-signer.log"
JAR="${GRAPH_RUN_SIGNER_JAR:-/app/pkg/api/build/libs/api.jar}"

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
  if curl -fsS "http://${SIGNER_BIND}:${SIGNER_PORT}/health" >/dev/null 2>&1; then
    echo "GraphRunSigner already running (pid $(cat "${PID_FILE}"))"
    echo "GraphRunSigner ready at http://${SIGNER_BIND}:${SIGNER_PORT}"
    exit 0
  fi
  echo "GraphRunSigner pid $(cat "${PID_FILE}") not healthy; restarting"
  stop_stale
fi

if [[ ! -f "${JAR}" ]]; then
  echo "GraphRunSigner jar missing; building offline"
  /app/pkg/ops/build-offline.sh
fi

nohup java -jar "${JAR}" \
  --server.address="${SIGNER_BIND}" \
  --server.port="${SIGNER_PORT}" \
  >"${LOG_FILE}" 2>&1 &
echo $! >"${PID_FILE}"
echo "Started GraphRunSigner pid $(cat "${PID_FILE}")"

for _ in $(seq 1 180); do
  if curl -fsS "http://${SIGNER_BIND}:${SIGNER_PORT}/health" >/dev/null 2>&1; then
    echo "GraphRunSigner ready at http://${SIGNER_BIND}:${SIGNER_PORT}"
    exit 0
  fi
  sleep 0.5
done

echo "GraphRunSigner failed health check; see ${LOG_FILE}" >&2
exit 1
