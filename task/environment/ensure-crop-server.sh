#!/bin/bash
set -euo pipefail

STATE_PATH="${STATE_PATH:-/var/lib/crop-planner/game_state.json}"
RESET_REQUESTED=0
if [ "${1:-}" = "--reset" ]; then
  RESET_REQUESTED=1
fi

server_ready() {
  python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8780/health', timeout=2).read()" 2>/dev/null
}

if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then
    if [ "${RESET_REQUESTED}" -eq 1 ]; then
      exec sudo -n /usr/local/bin/ensure-crop-server.sh --reset
    fi
    exec sudo -n /usr/local/bin/ensure-crop-server.sh
  fi
  echo "ensure-crop-server: root or passwordless sudo is required" >&2
  exit 1
fi

if server_ready && [ "${RESET_REQUESTED}" -eq 0 ]; then
  exit 0
fi

MODEL_SECRET="${MODEL_SECRET:-crop_plan_m0d3l_2026}"
LOG_SECRET="${LOG_SECRET:-crop_plan_l0g_2026}"
if [ -r /etc/crop-planner/env ]; then
  set -a
  # shellcheck source=/dev/null
  . /etc/crop-planner/env
  set +a
fi
export MODEL_SECRET LOG_SECRET

export STATE_PATH
mkdir -p /var/lib/crop-planner /var/log/crop-planner
chown cropd:cropd /var/lib/crop-planner /var/log/crop-planner
chmod 700 /var/lib/crop-planner /var/log/crop-planner

rm -f "${STATE_PATH}"
pkill -f '/opt/crop-planner/server.py' 2>/dev/null || true
sleep 1

nohup runuser -u cropd -- env \
  MODEL_SECRET="${MODEL_SECRET}" \
  LOG_SECRET="${LOG_SECRET}" \
  STATE_PATH="${STATE_PATH}" \
  python3 /opt/crop-planner/server.py \
  >>/var/log/crop-planner/server.log 2>&1 &

for _ in $(seq 1 30); do
  if server_ready; then
    exit 0
  fi
  sleep 1
done

echo "crop scoring server failed to start on http://127.0.0.1:8780" >&2
exit 1
