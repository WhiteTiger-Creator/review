#!/bin/bash
set -euo pipefail

readonly TEST_DIR="/tests"
readonly TEST_FILE="${TEST_DIR}/test_outputs.py"
readonly LOG_DIR="/logs/verifier"
readonly REWARD_FILE="${LOG_DIR}/reward.txt"
readonly CTRF_FILE="${LOG_DIR}/ctrf.json"
readonly PYTHON_BIN="/usr/bin/python3"

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/go/bin"
unset PYTHONHOME PYTHONPATH PYTHONSTARTUP PYTHONINSPECT
unset PYTEST_ADDOPTS PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD
export PYTHONSAFEPATH=1
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export GOPROXY=off
export GOSUMDB=off
export GOTELEMETRY=off
export GOTOOLCHAIN=local
export CGO_ENABLED=0

export SKYKINGDOM_BIN="${SKYKINGDOM_BIN:-/app/skykingdom/skykingdom}"
export SCENARIO_DIR="${SCENARIO_DIR:-/app/skykingdom/scenarios}"
export SKYKINGDOM_DIR="${SKYKINGDOM_DIR:-/app/skykingdom}"

mkdir -p "${LOG_DIR}"
printf '0\n' > "${REWARD_FILE}"

if [[ ! -x "${SKYKINGDOM_BIN}" && -f "${SKYKINGDOM_DIR}/main.go" ]]; then
  (cd "${SKYKINGDOM_DIR}" && go build -o skykingdom .) || true
fi

if [[ ! -x "${PYTHON_BIN}" || ! -r "${TEST_FILE}" ]]; then
    printf 'Verifier setup is incomplete.\n' >&2
    echo 0 > /logs/verifier/reward.txt
    exit 2
fi

cd "${TEST_DIR}"

set +e
"${PYTHON_BIN}" -I -m pytest \
    -c /dev/null \
    --rootdir="${TEST_DIR}" \
    --confcutdir="${TEST_DIR}" \
    -p no:cacheprovider \
    --ctrf "${CTRF_FILE}" \
    "${TEST_FILE}" \
    -rA
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
