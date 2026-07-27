#!/usr/bin/env bash
set -uo pipefail

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    mkdir -p /logs/verifier
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

mkdir -p /logs/verifier

verify_task() {
    local rc=0

    cd /tests
    export PYTHONSAFEPATH=1
    unset PYTHONPATH PYTHONHOME PYTEST_ADDOPTS

    local expected_tests collected_sorted collect_raw
    expected_tests=$(mktemp)
    collected_sorted=$(mktemp)
    collect_raw=$(mktemp)

    cat > "$expected_tests" <<'EOF'
test_outputs.py::test_outputs_exist
test_outputs.py::test_summary_schema
test_outputs.py::test_policy_schema_and_semantic_issuer
test_outputs.py::test_parallel_edges_distinct
test_outputs.py::test_alias_resolution
test_outputs.py::test_denied_edge_not_allow
test_outputs.py::test_retired_service_excluded
test_outputs.py::test_no_retired_mtls_fields
test_outputs.py::test_dossier_authority_beats_superseded
test_outputs.py::test_safe_algorithms_only
test_outputs.py::test_audit_complete_run
test_outputs.py::test_coverage_no_gaps
test_outputs.py::test_idempotent_rerun
test_outputs.py::test_both_oidc_revisions
test_outputs.py::test_protected_fixtures_unchanged
test_outputs.py::test_transport_not_in_policy
EOF
    sort "$expected_tests" -o "$expected_tests"

    if ! /usr/bin/python3 -P -m pytest --collect-only -q test_outputs.py > "$collect_raw" 2>&1; then
        rc=1
    fi

    grep -E '^test_outputs.py::' "$collect_raw" | sort > "$collected_sorted"
    if ! cmp -s "$expected_tests" "$collected_sorted"; then
        rc=1
    fi
    if [ "$(wc -l < "$collected_sorted")" -ne 16 ]; then
        rc=1
    fi

    if ! /usr/bin/python3 -P -m pytest \
        --ctrf /logs/verifier/ctrf.json \
        --junitxml /logs/verifier/junit.xml \
        test_outputs.py \
        -rA; then
        rc=1
    fi

    if ! /usr/bin/python3 -P <<'PY'
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

junit = Path("/logs/verifier/junit.xml")
ctrf = Path("/logs/verifier/ctrf.json")
if not junit.is_file() or not ctrf.is_file():
    sys.exit(1)
if ctrf.stat().st_size == 0:
    sys.exit(1)

root = ET.parse(junit).getroot()
cases = root.findall(".//testcase")
if len(cases) != 16:
    sys.exit(1)
for case in cases:
    if case.find("failure") is not None:
        sys.exit(1)
    if case.find("error") is not None:
        sys.exit(1)
    if case.find("skipped") is not None:
        sys.exit(1)
sys.exit(0)
PY
    then
        rc=1
    fi

    rm -f "$expected_tests" "$collected_sorted" "$collect_raw"
    return "$rc"
}

verify_task
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
