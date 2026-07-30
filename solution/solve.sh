#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH_FILE="${SCRIPT_DIR}/varnish-grace-handover.patch"

cd /srv/mirrorveil

if [[ -x /srv/mirrorveil/bin/stop-cache-stack ]]; then
  /srv/mirrorveil/bin/stop-cache-stack || true
fi

if patch -p1 --dry-run -i "${PATCH_FILE}" >/tmp/mirrorveil-patch-forward.out 2>/tmp/mirrorveil-patch-forward.err; then
  patch -p1 -i "${PATCH_FILE}"
elif patch -p1 -R --dry-run -i "${PATCH_FILE}" >/tmp/mirrorveil-patch-reverse.out 2>/tmp/mirrorveil-patch-reverse.err; then
  echo "patch already applied"
else
  echo "patch does not apply in forward or reverse direction" >&2
  echo "--- forward stderr ---" >&2
  cat /tmp/mirrorveil-patch-forward.err >&2 || true
  echo "--- forward stdout ---" >&2
  cat /tmp/mirrorveil-patch-forward.out >&2 || true
  echo "--- reverse stderr ---" >&2
  cat /tmp/mirrorveil-patch-reverse.err >&2 || true
  exit 1
fi

chmod 0755 /srv/mirrorveil/bin/reload-cache-policy /srv/mirrorveil/bin/start-cache-stack /srv/mirrorveil/bin/compute-vcl-label || true

/srv/mirrorveil/build-cache-stack.sh
/srv/mirrorveil/bin/start-cache-stack
/srv/mirrorveil/bin/wait-for-cache stack-ready

exit 0
