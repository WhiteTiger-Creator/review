#!/bin/bash
set -euo pipefail

ROOT=/srv/mirrorveil
# shellcheck source=/dev/null
source "${ROOT}/policy/topology.conf"
# shellcheck source=/dev/null
source "${ROOT}/policy/control.conf"
# shellcheck source=/dev/null
source "${ROOT}/policy/cache-limits.conf"
# shellcheck source=/dev/null
source "${ROOT}/policy/host-map.conf"

fail() {
  echo "build-cache-stack: $*" >&2
  exit 1
}

require_var() {
  local name="$1"
  [[ -n "${!name:-}" ]] || fail "missing policy variable ${name}"
}

for script in \
  "${ROOT}/bin/start-cache-stack" \
  "${ROOT}/bin/stop-cache-stack" \
  "${ROOT}/bin/reload-cache-policy" \
  "${ROOT}/bin/cache-control" \
  "${ROOT}/bin/inspect-cache" \
  "${ROOT}/bin/wait-for-cache" \
  "${ROOT}/build-cache-stack.sh" \
  "${ROOT}/examples/seed-origins.sh" \
  "${ROOT}/examples/make-large-object.sh" \
  "${ROOT}/examples/verify-stack.sh"
do
  bash -n "${script}" || fail "bash -n failed for ${script}"
done

require_var CACHE_PORT
require_var MGMT_PORT
require_var PRIMARY_PORT
require_var SECONDARY_PORT
require_var VARNISH_STORAGE_NAME
require_var PRIMARY_PID_FILE
require_var SECONDARY_PID_FILE
require_var VARNISH_PID_FILE
require_var PRIMARY_ORIGIN_ROOT
require_var SECONDARY_ORIGIN_ROOT
require_var CONTROL_MARKER
require_var CONTROL_HEADER
require_var FRESHNESS_SECONDS
require_var GRACE_SECONDS
require_var KEEP_SECONDS
require_var HOST_AURORA
require_var HOST_BASALT

# Never print the control marker.
[[ "${CONTROL_MARKER}" != *[[:space:]]* ]] || fail "control marker must be a single token"

ports=("${CACHE_PORT}" "${MGMT_PORT}" "${PRIMARY_PORT}" "${SECONDARY_PORT}")
uniq_ports="$(printf '%s\n' "${ports[@]}" | sort -u | wc -l | tr -d ' ')"
[[ "${uniq_ports}" == "4" ]] || fail "ports must be unique"

[[ "${PRIMARY_PID_FILE}" != "${SECONDARY_PID_FILE}" ]] || fail "origin pid files must differ"
[[ "${PRIMARY_ORIGIN_ROOT}" != "${SECONDARY_ORIGIN_ROOT}" ]] || fail "origin roots must differ"

mkdir -p "${PRIMARY_PREFIX}/logs" "${SECONDARY_PREFIX}/logs" "${VARNISH_WORK_DIR}"
nginx -t -c "${ROOT}/nginx/primary.conf" -p "${PRIMARY_PREFIX}/" || fail "primary nginx config invalid"
nginx -t -c "${ROOT}/nginx/secondary.conf" -p "${SECONDARY_PREFIX}/" || fail "secondary nginx config invalid"

varnishd -C -f "${ENTRY_VCL}" >/tmp/mirrorveil-build-vcl.out 2>/tmp/mirrorveil-build-vcl.err \
  || { cat /tmp/mirrorveil-build-vcl.err >&2; fail "entry VCL compile failed"; }

[[ -x "${ROOT}/examples/seed-origins.sh" ]] || fail "seed-origins.sh not executable"
[[ -x "${ROOT}/examples/make-large-object.sh" ]] || fail "make-large-object.sh not executable"

# Confirm generators are syntactically valid and deterministic helpers exist.
bash -n "${ROOT}/examples/seed-origins.sh"
bash -n "${ROOT}/examples/make-large-object.sh"

echo "build-cache-stack: validation ok"
exit 0
