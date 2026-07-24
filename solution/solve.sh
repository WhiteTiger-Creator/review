#!/bin/bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/app}"
SRC_DIR="${APP_ROOT}/src"
# Harbor mounts the solution at /solution (not /app/solution); resolve relative to this script.
SOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[oracle] repairing periodctl and host control plane"

# Copy corrected files to the target directory
cp "${SOL_DIR}/periodctl" "${SRC_DIR}/periodctl"
cp "${SOL_DIR}/reconciler.py" "${SRC_DIR}/reconciler.py"
cp "${SOL_DIR}/ledger.py" "${SRC_DIR}/ledger.py"

chmod 0755 "${SRC_DIR}/periodctl"
chmod 0644 "${SRC_DIR}/reconciler.py"
chmod 0644 "${SRC_DIR}/ledger.py"

echo "[oracle] restoring period-close host layout"
mkdir -p /etc/period-close /var/lib/period-close
cp "${APP_ROOT}/data/window.json" /etc/period-close/window.json
chmod 0644 /etc/period-close/window.json
chmod 0755 /var/lib/period-close
ln -sfn "${SRC_DIR}/periodctl" /usr/local/sbin/periodctl

if [[ -f /etc/systemd/system/period-close.service ]]; then
    chmod 0644 /etc/systemd/system/period-close.service
fi

echo "[oracle] solution applied successfully"
