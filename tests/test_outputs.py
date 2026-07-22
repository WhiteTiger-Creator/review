"""Exact-count checks for the modal counting tool against a held-out reference."""

import os
import subprocess
import time

import pytest

TOOL = "/app/spectral_count"
OPERATOR = "/app/operator.mtx"
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
GRADED_QRY = os.path.join(FIXTURES, "graded.qry")

EXPECTED = [9992, 9991, 9990, 1008, 30376, 394049]


def _run_tool():
    proc = subprocess.run(
        [TOOL, OPERATOR, GRADED_QRY],
        capture_output=True,
        text=True,
        timeout=850,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"tool exited {proc.returncode}: {proc.stderr[-2000:]}")
    out = [line for line in proc.stdout.split() if line.strip() != ""]
    return [int(x) for x in out]


RUNTIME_BUDGET_SECONDS = 800.0

try:
    _t0 = time.time()
    ACTUAL = _run_tool()
    ELAPSED = time.time() - _t0
    RUN_ERROR = None
except Exception as exc:  # noqa: BLE001
    ACTUAL = []
    ELAPSED = float("inf")
    RUN_ERROR = str(exc)


def _check(idx):
    assert RUN_ERROR is None, f"tool failed to run: {RUN_ERROR}"
    assert idx < len(ACTUAL), f"missing output for case {idx}"
    assert ACTUAL[idx] == EXPECTED[idx], (
        f"case {idx}: expected {EXPECTED[idx]}, got {ACTUAL[idx]}"
    )


def test_tool_built():
    """The counting tool was built at the expected path."""
    assert os.path.exists(TOOL), (
        "spectral_count binary not found at /app/spectral_count"
    )


def test_operator_fetched():
    """The operator was fetched to the expected path before grading."""
    assert os.path.exists(OPERATOR), "operator not fetched to /app/operator.mtx"


def test_output_length():
    """The tool emits exactly one count per graded case."""
    assert RUN_ERROR is None, f"tool failed to run: {RUN_ERROR}"
    assert len(ACTUAL) == len(EXPECTED), (
        f"expected {len(EXPECTED)} counts, got {len(ACTUAL)}"
    )


def test_runtime_within_budget():
    """The tool returns all counts within the runtime budget, which a dense or
    diagonalizing approach on this operator cannot meet."""
    assert RUN_ERROR is None, f"tool failed to run: {RUN_ERROR}"
    assert ELAPSED < RUNTIME_BUDGET_SECONDS, (
        f"tool took {ELAPSED:.0f}s, over the {RUNTIME_BUDGET_SECONDS:.0f}s budget"
    )


def test_base_inertia_count():
    """The unmodified-operator count below the shift is exact."""
    _check(0)


def test_modified_count_alpha():
    """The first modified-operator count is exact, not the unmodified count."""
    _check(1)


def test_modified_count_beta():
    """The second modified-operator count is exact under a stronger modification."""
    _check(2)


@pytest.mark.parametrize("idx", range(3, 6))
def test_remaining_case_counts(idx):
    """Every remaining graded case count is exact."""
    _check(idx)
