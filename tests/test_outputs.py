import glob
import json
import os
import re
import subprocess
import tempfile

import pytest

APP = "/app"
TESTS = "/tests"
FIX = os.path.join(TESTS, "fixtures")

GRADER = tempfile.mkdtemp(prefix="arimaa_retro_grader_")

BANNED_INCLUDES = [
    "stockfish",
    "fairy",
    "leela",
    "syzygy",
    "gaviota",
    "python-chess",
    "nnue",
]

MIN_HIDDEN = 60
MIN_THROUGHPUT = 40
MIN_BATTERY = 150
MIN_ZERO_COUNT = 4


def _build_agent():
    srcs = sorted(glob.glob(os.path.join(APP, "src", "*.cpp")))
    if not srcs:
        return None
    out = os.path.join(GRADER, "agent_retro")
    cmd = ["g++", "-O2", "-std=c++17", *srcs, "-o", out]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return out if r.returncode == 0 and os.path.exists(out) else None


AGENT = _build_agent()


def _load(name):
    with open(os.path.join(FIX, name)) as fh:
        return json.load(fh)


HIDDEN = _load("hidden.json")
THROUGHPUT = _load("throughput.json")
VISIBLE = _load("visible.json")
ANCHORS = _load("anchors.json")
TWINS = [fx for fx in HIDDEN if "twin_of" in fx]


def run_lines(binary, queries, timeout):
    if binary is None:
        return None
    inp = "".join(f"{q['placement']} {q['mover']}\n" for q in queries)
    try:
        r = subprocess.run(
            [binary],
            input=inp,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    out = r.stdout.split()
    if len(out) != len(queries):
        return None
    vals = []
    for tok in out:
        if not re.fullmatch(r"-?\d+", tok):
            return None
        vals.append(int(tok))
    return vals


def run1(binary, fx, timeout=300):
    vals = run_lines(binary, [fx], timeout)
    return None if vals is None else vals[0]


def _agent_include_lines():
    lines = []
    for p in sorted(glob.glob(os.path.join(APP, "src", "*.cpp"))) + sorted(
        glob.glob(os.path.join(APP, "src", "*.hpp"))
    ):
        with open(p, errors="ignore") as fh:
            for line in fh:
                if line.lstrip().startswith("#include"):
                    lines.append(line.strip().lower())
    return lines


def test_builds():
    """The agent sources under /app/src compile into a runnable program."""
    assert AGENT is not None, "agent sources under /app/src did not compile"


def test_battery_is_large_enough():
    """The graded battery holds well over sixty executed per-query cases."""
    assert len(HIDDEN) >= MIN_HIDDEN
    assert len(THROUGHPUT) >= MIN_THROUGHPUT
    assert len(HIDDEN) + len(THROUGHPUT) + len(VISIBLE) >= MIN_BATTERY


@pytest.mark.parametrize(
    "a", [a for a in ANCHORS if a.get("hand_derived")], ids=lambda a: a["id"]
)
def test_hand_derived_anchor(a):
    """The agent reproduces each hand derived anchor count."""
    assert run1(AGENT, a) == a["expected"]


def test_capture_free_sector_anchor():
    """The agent reproduces the hand derived capture free predecessor cone."""
    a = next(x for x in ANCHORS if x["id"] == "lone_rabbit")
    assert run1(AGENT, a) == a["expected"]


@pytest.mark.parametrize("fx", HIDDEN, ids=[f["id"] for f in HIDDEN])
def test_hidden_agent_matches_expected(fx):
    """On each hidden query the agent count equals the independently recomputed
    count."""
    assert run1(AGENT, fx) == fx["expected"]


def test_throughput_batch_within_budget():
    """The agent answers the full throughput batch exactly within the disclosed
    time budget."""
    vals = run_lines(AGENT, THROUGHPUT, timeout=1200)
    assert vals is not None, (
        "batch failed, produced malformed output, or exceeded 1200s"
    )
    for fx, got in zip(THROUGHPUT, vals):
        assert got == fx["expected"], fx["id"]


@pytest.mark.parametrize("fx", VISIBLE, ids=[f["id"] for f in VISIBLE])
def test_visible_agent_matches_expected(fx):
    """On each visible sample the agent matches the published answer."""
    assert run1(AGENT, fx) == fx["expected"]


@pytest.mark.parametrize("fx", TWINS, ids=[f["id"] for f in TWINS])
def test_metamorphic_twin_counts_match(fx):
    """A mirrored or colour swapped query keeps the identical count."""
    src = next(h for h in HIDDEN if h["id"] == fx["twin_of"])
    assert fx["expected"] == src["expected"]
    assert run1(AGENT, fx) == run1(AGENT, src) == fx["expected"]


def test_zero_count_queries_are_graded():
    """The battery grades queries whose true count is zero."""
    zeros = [fx for fx in HIDDEN if fx["expected"] == 0]
    assert len(zeros) >= MIN_ZERO_COUNT
    for fx in zeros:
        assert run1(AGENT, fx) == 0


def test_agent_is_deterministic():
    """The agent returns the same integer on a repeated identical query."""
    for fx in (HIDDEN[0], HIDDEN[len(HIDDEN) // 2], HIDDEN[-1]):
        assert run1(AGENT, fx) == run1(AGENT, fx)


def test_no_vendored_engine_include():
    """The agent sources do not include a known engine, binding, or tablebase
    library."""
    includes = _agent_include_lines()
    for line in includes:
        for banned in BANNED_INCLUDES:
            assert banned not in line, f"forbidden include: {line}"
