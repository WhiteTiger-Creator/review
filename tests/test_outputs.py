"""Exact census checks for the relaxation census tool against a held-out reference."""

import os
import subprocess
import time

import pytest

TOOL = "/app/mode_census"
OPERATOR = "/app/operator.mtx"
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
GRADED_CSE = os.path.join(FIXTURES, "graded.cse")

EXPECTED = [8364, 8365, 51995, 51995, 310105, 971584]

RUNTIME_BUDGET_SECONDS = 800.0


def _run_tool():
    proc = subprocess.run(
        [TOOL, OPERATOR, GRADED_CSE],
        capture_output=True,
        text=True,
        timeout=850,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"tool exited {proc.returncode}: {proc.stderr[-2000:]}")
    out = [line for line in proc.stdout.split() if line.strip() != ""]
    return [int(x) for x in out]


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
    assert idx < len(ACTUAL), f"missing census for case {idx}"
    assert ACTUAL[idx] == EXPECTED[idx], (
        f"case {idx}: expected {EXPECTED[idx]}, got {ACTUAL[idx]}"
    )


def test_tool_built():
    """The census tool was built at the expected path."""
    assert os.path.exists(TOOL), "mode_census binary not found at /app/mode_census"


def test_operator_fetched():
    """The conductance operator was fetched to the expected path before grading."""
    assert os.path.exists(OPERATOR), "operator not fetched to /app/operator.mtx"


def test_census_line_count():
    """The tool emits exactly one census per graded case."""
    assert RUN_ERROR is None, f"tool failed to run: {RUN_ERROR}"
    assert len(ACTUAL) == len(EXPECTED), (
        f"expected {len(EXPECTED)} censuses, got {len(ACTUAL)}"
    )


def test_runtime_within_budget():
    """The tool returns every census within the runtime budget, which a dense or
    diagonalizing treatment of the pair at this scale cannot meet."""
    assert RUN_ERROR is None, f"tool failed to run: {RUN_ERROR}"
    assert ELAPSED < RUNTIME_BUDGET_SECONDS, (
        f"tool took {ELAPSED:.0f}s, over the {RUNTIME_BUDGET_SECONDS:.0f}s budget"
    )


def test_bare_pair_census():
    """The unpatched pair's census below the shift is exact, which pins the rule
    that turns the distributed operator into the second member of the pair."""
    _check(0)


def test_conductance_patch_census():
    """A case carrying conductance side terms only is exact, not the bare census."""
    _check(1)


def test_capacitance_patch_census():
    """A case carrying capacitance side terms only is exact; the shift scales how
    that side enters, so an unscaled treatment lands on a different integer."""
    _check(2)


def test_two_sided_patch_census():
    """A case carrying terms on both sides of the pair at once is exact."""
    _check(3)


@pytest.mark.parametrize("idx", range(4, 6))
def test_remaining_case_censuses(idx):
    """Every remaining graded case census is exact at its own shift and patch mix."""
    _check(idx)
