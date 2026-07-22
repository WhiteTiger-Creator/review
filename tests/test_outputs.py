"""Behavioral verifier for the prepaid gondola-schedule threshold report.

Each test writes a line-config file and a boarding-stream file to a temp
directory, runs report.py in /app as a black box, and asserts the emitted
ledger against the contract in /app/docs/spec.md. The verifier supplies its
own hand fixtures and a static differential corpus of pre-computed
expectations for a broad cross-check.
"""

import json
import os
import subprocess
import tempfile

import pytest

APP_DIR = os.environ.get("APP_DIR", "/app")
REPORT = os.path.join(APP_DIR, "report.py")


@pytest.fixture(scope="module", autouse=True)
def check_report():
    """Confirm the data-processing tool is present before exercising it."""
    assert os.path.exists(REPORT), f"report.py not found at {REPORT}"


def run(config_text, events_text):
    """Run the tool on the two input texts; return (rc, stdout, stderr)."""
    d = tempfile.mkdtemp()
    cfg = os.path.join(d, "line.cfg")
    ev = os.path.join(d, "usage.log")
    with open(cfg, "w") as f:
        f.write(config_text)
    with open(ev, "w") as f:
        f.write(events_text)
    try:
        proc = subprocess.run(
            ["python3", REPORT, cfg, ev], capture_output=True, text=True, timeout=60
        )
    finally:
        os.unlink(cfg)
        os.unlink(ev)
        os.rmdir(d)
    return proc.returncode, proc.stdout, proc.stderr


def ledger(config_text, events_text):
    """Run a valid scenario and return its ledger as a list of output lines."""
    rc, out, err = run(config_text, events_text)
    assert rc == 0, f"unexpected nonzero exit ({rc}); stderr={err!r}"
    return out.splitlines()


# ---------------------------------------------------------------------------
# Core allocation / surge hand fixtures
# ---------------------------------------------------------------------------
def test_cap_blocks_immediately():
    """A boarding event that would exceed the gondola limit is denied at once
    and leaves the counter untouched, so a later in-bounds boarding event still
    succeeds."""
    cfg = "GOND a 10 12 5\nLINE g 1000 2000 5\nROUTE a g\n"
    ev = "0 BOARD a 13\n0 BOARD a 5\n"
    assert ledger(cfg, ev) == ["0 REJECT GOND_LIMIT", "0 BOARDED"]


def test_plan_cap_checked_after_sub():
    """When the gondola allocation permits but the line limit does not, the
    denial cites LINE_LIMIT."""
    cfg = "GOND a 1000 1000 5\nLINE g 5 8 5\nROUTE a g\n"
    ev = "0 BOARD a 9\n"
    assert ledger(cfg, ev) == ["0 REJECT LINE_LIMIT"]


def test_throttle_cross_starts_boost_and_allows_within():
    """Crossing the threshold opens a surge window and announces
    SURGE_START; further boarding events within the window and under the limit are
    still granted normally."""
    cfg = "GOND a 10 100 3\nLINE g 1000 2000 9\nROUTE a g\n"
    ev = "2 BOARD a 11\n3 BOARD a 1\n"
    assert ledger(cfg, ev) == ["2 BOARDED", "2 SURGE_START GOND a", "3 BOARDED"]


def test_inclusive_boost_boundary_within_window_allows_normally():
    """While the surge window is open, boarding events up to the limit are granted
    normally with no standby-pool draw; the far edge is inclusive."""
    cfg = "GOND a 10 100 3\nLINE g 1000 2000 9\nROUTE a g\n"
    # window opens at tick 2 -> open through tick 5 inclusive.
    ev = "2 BOARD a 11\n5 BOARD a 1\n"
    assert ledger(cfg, ev) == ["2 BOARDED", "2 SURGE_START GOND a", "5 BOARDED"]


def test_recross_restarts_full_window_not_resume():
    """After a cancel, re-crossing the threshold opens a FULL new
    window from the later crossing rather than resuming the earlier window's
    remainder."""
    cfg = "GOND a 5 100 3\nLINE g 1000 2000 50\nROUTE a g\n"
    # t1 cross (window t1..t4); t2 credit under threshold -> cancel; t3 re-cross
    # -> restart (window t3..t6).
    ev = "1 BOARD a 6\n2 ALIGHT a 3\n3 BOARD a 3\n"
    assert ledger(cfg, ev) == [
        "1 BOARDED",
        "1 SURGE_START GOND a",
        "3 BOARDED",
        "3 SURGE_START GOND a",
    ]


def test_no_repeat_boost_start_while_staying_over_throttle():
    """Staying over the threshold across several boarding events announces
    SURGE_START only once, at the opening crossing."""
    cfg = "GOND a 5 100 9\nLINE g 1000 2000 50\nROUTE a g\n"
    ev = "0 BOARD a 6\n1 BOARD a 1\n2 BOARD a 1\n"
    assert ledger(cfg, ev) == [
        "0 BOARDED",
        "0 SURGE_START GOND a",
        "1 BOARDED",
        "2 BOARDED",
    ]


def test_credit_under_throttle_cancels_timer_no_output():
    """A credit that drops usage back under the threshold cancels the
    running window and emits no line (it repays no pool debt); a later usage
    event that stays under the threshold is a plain BOARDED."""
    cfg = "GOND a 5 100 2\nLINE g 1000 2000 9\nROUTE a g\n"
    ev = "0 BOARD a 6\n1 ALIGHT a 3\n9 BOARD a 2\n"
    assert ledger(cfg, ev) == ["0 BOARDED", "0 SURGE_START GOND a", "9 BOARDED"]


# ---------------------------------------------------------------------------
# Shared standby pool: standby, denial, and the decisive LIFO refund-unwind
# ---------------------------------------------------------------------------
def test_boost_expired_borrows_from_pool_without_boost_start():
    """Once an allocation's surge has expired, the shortfall above its threshold
    ceiling is borrowed from the line standby pool instead of denied; the standby
    draws on a separate pool and does not open a surge window."""
    cfg = "GOND a 1000 100000 9\nLINE g 5 100 2 20\nROUTE a g\n"
    # t0 use 6 -> line over threshold within surge (window 0..2) -> SURGE_START.
    # t5 use 4 -> line surge expired, normal room 0 -> standby 4 from pool.
    ev = "0 BOARD a 6\n5 BOARD a 4\n"
    assert ledger(cfg, ev) == [
        "0 BOARDED",
        "0 SURGE_START LINE g",
        "5 BOARDED",
        "5 STANDBY a 4",
    ]


def test_no_pool_means_boost_expired_use_is_denied():
    """With the default pool of zero, a boarding event that exceeds the
    threshold-surge ceiling has nowhere to standby from and is denied as
    pool-exhausted."""
    cfg = "GOND a 1000 100000 0\nLINE g 5 100 0\nROUTE a g\n"
    # t0 use 6 over threshold within surge (grace 0 -> window only tick 0).
    # t1 use 1 -> surge expired, room 0, no pool -> STANDBY_EMPTY.
    ev = "0 BOARD a 6\n1 BOARD a 1\n"
    assert ledger(cfg, ev) == [
        "0 BOARDED",
        "0 SURGE_START LINE g",
        "1 REJECT STANDBY_EMPTY",
    ]


def test_pool_exhausted_is_all_or_nothing():
    """A shortfall the free pool cannot fully cover denies the whole boarding event
    and changes nothing, so a smaller request that does fit is later allowed and
    borrows."""
    cfg = "GOND a 1000 100000 0\nLINE g 5 100 0 3\nROUTE a g\n"
    # t0 use 6 -> over threshold (window tick 0) SURGE_START.
    # t1 use 4 -> shortfall 4 > free pool 3 -> REJECT (no partial standby).
    # t2 use 3 -> shortfall 3 == pool 3 -> BOARDED + STANDBY 3.
    ev = "0 BOARD a 6\n1 BOARD a 4\n2 BOARD a 3\n"
    assert ledger(cfg, ev) == [
        "0 BOARDED",
        "0 SURGE_START LINE g",
        "1 REJECT STANDBY_EMPTY",
        "2 BOARDED",
        "2 STANDBY a 3",
    ]


def test_credit_repays_debt_lifo_newest_first():
    """A credit first repays the gondola's pool debt, unwinding borrows
    newest-first; the RETURN line reports the total returned to the pool."""
    cfg = "GOND a 1000 100000 0\nLINE g 5 100 0 20\nROUTE a g\n"
    # t0 use 6 (over threshold, window tick 0) SURGE_START.
    # t1 standby 3, t2 standby 2 -> debt stack [3, 2].
    # t3 credit 4 -> return 2 (newest) then 2 of the 3 -> repaid 4, debt [1].
    ev = "0 BOARD a 6\n1 BOARD a 3\n2 BOARD a 2\n3 ALIGHT a 4\n"
    assert ledger(cfg, ev) == [
        "0 BOARDED",
        "0 SURGE_START LINE g",
        "1 BOARDED",
        "1 STANDBY a 3",
        "2 BOARDED",
        "2 STANDBY a 2",
        "3 RETURN a 4",
    ]


def test_credit_repays_debt_first_then_reduces_own_usage():
    """When a credit is larger than the outstanding debt, it settles the debt
    first (returning those MB to the pool) and only the remainder reduces the
    gondola's own usage, which can in turn cancel a surge window."""
    cfg = "GOND a 1000 100000 0\nLINE g 5 100 0 20\nROUTE a g\n"
    # t0 use 6 over threshold SURGE_START (grant 6). t1 standby 3 (debt [3]).
    # t2 credit 5 -> return 3 (debt empty), remaining 2 reduces own usage 6 -> 4.
    #   usage 4 <= soft 5 -> line window cancels (no extra output).
    ev = "0 BOARD a 6\n1 BOARD a 3\n2 ALIGHT a 5\n"
    assert ledger(cfg, ev) == [
        "0 BOARDED",
        "0 SURGE_START LINE g",
        "1 BOARDED",
        "1 STANDBY a 3",
        "2 RETURN a 3",
    ]


def test_borrowed_mb_credited_to_pool_reenable_a_later_borrow():
    """Repaying debt returns capacity to the shared standby pool, so a later usage
    event that would otherwise be pool-exhausted can standby again."""
    cfg = "GOND a 1000 100000 0\nLINE g 5 100 0 3\nROUTE a g\n"
    # t0 use 6 SURGE_START. t1 standby 3 (pool now full).
    # t2 use 1 -> shortfall 1 > free 0 -> REJECT STANDBY_EMPTY.
    # t3 credit 3 -> return 3 (pool free again). t4 use 2 -> standby 2.
    ev = "0 BOARD a 6\n1 BOARD a 3\n2 BOARD a 1\n3 ALIGHT a 3\n4 BOARD a 2\n"
    assert ledger(cfg, ev) == [
        "0 BOARDED",
        "0 SURGE_START LINE g",
        "1 BOARDED",
        "1 STANDBY a 3",
        "2 REJECT STANDBY_EMPTY",
        "3 RETURN a 3",
        "4 BOARDED",
        "4 STANDBY a 2",
    ]


def test_contended_pool_is_deterministic_across_subscribers():
    """Two subscribers share one line pool. Borrows are charged to whoever uses
    data, a contended pool denies the gondola who arrives once it is
    exhausted, and a repayment by one gondola frees capacity that the other
    can then standby, all determined by stream order."""
    cfg = (
        "GOND a 1000 100000 0\nGOND b 1000 100000 0\n"
        "LINE g 5 100 0 4\nROUTE a g\nROUTE b g\n"
    )
    # t0 a use 6 -> line over threshold (window tick 0) SURGE_START.
    # t1 b use 3 -> surge expired, room 0 -> standby 3 (b's debt, reserve_used 3).
    # t1 a use 2 -> shortfall 2 > free 1 -> REJECT STANDBY_EMPTY.
    # t2 b credit 3 -> return 3 (pool free). t3 a use 2 -> standby 2.
    ev = "0 BOARD a 6\n1 BOARD b 3\n1 BOARD a 2\n2 ALIGHT b 3\n3 BOARD a 2\n"
    assert ledger(cfg, ev) == [
        "0 BOARDED",
        "0 SURGE_START LINE g",
        "1 BOARDED",
        "1 STANDBY b 3",
        "1 REJECT STANDBY_EMPTY",
        "2 RETURN b 3",
        "3 BOARDED",
        "3 STANDBY a 2",
    ]


def test_lifo_unwind_across_interleaved_borrows_and_credit():
    """Interleaving borrows of different sizes and then crediting exactly one
    standby's worth pops only the newest standby off the debt stack, leaving the
    older ones intact (a later credit then unwinds those oldest-last)."""
    cfg = "GOND a 1000 100000 0\nLINE g 5 100 0 30\nROUTE a g\n"
    # t0 use 6 SURGE_START (grant 6, over threshold). debt [].
    # t1 standby 4, t2 standby 7, t3 standby 2 -> debt [4, 7, 2], reserve_used 13.
    # t4 credit 2 -> repays exactly the newest standby (2) -> debt [4, 7].
    # t5 credit 7 -> repays the 7 -> debt [4].
    # t6 credit 10 -> repays the 4 (debt empty), remaining 6 reduces usage 6 -> 0.
    ev = (
        "0 BOARD a 6\n1 BOARD a 4\n2 BOARD a 7\n3 BOARD a 2\n"
        "4 ALIGHT a 2\n5 ALIGHT a 7\n6 ALIGHT a 10\n"
    )
    assert ledger(cfg, ev) == [
        "0 BOARDED",
        "0 SURGE_START LINE g",
        "1 BOARDED",
        "1 STANDBY a 4",
        "2 BOARDED",
        "2 STANDBY a 7",
        "3 BOARDED",
        "3 STANDBY a 2",
        "4 RETURN a 2",
        "5 RETURN a 7",
        "6 RETURN a 4",
    ]


def test_credit_cancel_then_recross_grants_normally_not_denied():
    """A credit that drops a line back to or under the threshold cancels
    its window; once the window is cancelled the allocation is no longer
    surge-expired, so a later boarding event that crosses the threshold
    again is granted normally (opening a fresh window) instead of being held to
    the threshold ceiling or denied."""
    cfg = "GOND u 7 15 1\nLINE g 5 12 4\nROUTE u g\n"
    # t3 use 6 -> line over threshold (window 3..7) SURGE_START.
    # t4 credit 3 -> line usage 6 -> 3 (<= soft 5) -> window cancels (no output).
    # t8 use 5 -> line usage 3 -> 8: under-threshold start means ceiling is limit,
    #   so all 5 granted normally and the crossing opens a fresh window. The
    #   line is NOT surge-expired here and is well under its limit (12).
    ev = "3 BOARD u 6\n4 ALIGHT u 3\n8 BOARD u 5\n"
    assert ledger(cfg, ev) == [
        "3 BOARDED",
        "3 SURGE_START LINE g",
        "8 BOARDED",
        "8 SURGE_START GOND u",
        "8 SURGE_START LINE g",
    ]


def test_multisub_credit_cancel_then_recross_and_cap_after_window():
    """A longer multi-gondola timeline that interleaves a line window
    cancelled by a credit, a later normal re-grant that reopens the window, pool
    exhaustion, and limit denials. The line usage must be tracked exactly across
    all of this so that a boarding event the cancelled window would otherwise hold
    back is granted, and later denials cite the correct (gondola vs line) limit
    reason."""
    cfg = (
        "LINE g0 5 12 4\nLINE g1 2 7 0\n"
        "GOND u0 7 15 1\nROUTE u0 g0\nGOND u1 8 10 2\nROUTE u1 g0\n"
    )
    ev = (
        "1 ALIGHT u1 6\n3 BOARD u0 6\n3 ALIGHT u1 3\n7 BOARD u1 2\n8 BOARD u0 5\n"
        "12 BOARD u0 2\n13 BOARD u0 7\n15 BOARD u0 7\n18 BOARD u1 6\n21 ALIGHT u1 6\n"
    )
    assert ledger(cfg, ev) == [
        "3 BOARDED",
        "3 SURGE_START LINE g0",
        "7 BOARDED",
        "8 BOARDED",
        "8 SURGE_START GOND u0",
        "8 SURGE_START LINE g0",
        "12 REJECT STANDBY_EMPTY",
        "13 REJECT GOND_LIMIT",
        "15 REJECT GOND_LIMIT",
        "18 REJECT LINE_LIMIT",
    ]


def test_two_sub_plan_window_cancel_and_independent_recross():
    """Two subscribers share a line whose window is opened by one gondola's
    usage and then cancelled when that gondola credits back under the line
    threshold; a second gondola crossing the line threshold afterwards opens a
    fresh window and is granted normally rather than treated as still over an
    expired window."""
    cfg = "GOND x 6 20 1\nGOND y 6 20 1\nLINE h 8 14 2 5\nROUTE x h\nROUTE y h\n"
    ev = "0 BOARD x 10\n1 BOARD y 4\n3 ALIGHT x 10\n4 BOARD y 6\n"
    assert ledger(cfg, ev) == [
        "0 BOARDED",
        "0 SURGE_START GOND x",
        "0 SURGE_START LINE h",
        "1 BOARDED",
        "4 BOARDED",
        "4 SURGE_START GOND y",
        "4 SURGE_START LINE h",
    ]


def test_borrowed_mb_excluded_from_usage_on_later_use():
    """Borrowed MB are parked in the standby pool and never counted in usage, so
    a later boarding event's limit check sees only the granted usage; a boarding event
    that would appear to exceed the limit if borrowed MB were counted is in fact
    allowed and borrows again."""
    cfg = "GOND u 1000 100000 0\nLINE g 5 10 0 20\nROUTE u g\n"
    # t0 use 6 -> line usage 6 (window tick 0) SURGE_START.
    # t1 use 4 -> surge expired, room 0 -> standby 4 (parked; line usage stays 6).
    # t2 use 3 -> line usage 6 + 3 = 9 <= limit 10 (borrowed 4 NOT counted, or
    #   6 + 4 + 3 = 13 > 10 would wrongly deny) -> standby 3.
    ev = "0 BOARD u 6\n1 BOARD u 4\n2 BOARD u 3\n"
    assert ledger(cfg, ev) == [
        "0 BOARDED",
        "0 SURGE_START LINE g",
        "1 BOARDED",
        "1 STANDBY u 4",
        "2 BOARDED",
        "2 STANDBY u 3",
    ]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "cfg,ev",
    [
        ("GOND a 10 5 3\nLINE g 100 200 3\nROUTE a g\n", "0 BOARD a 1\n"),
        ("GOND a 10 20 3\nLINE g 100 200 3\nROUTE a g\n", "0 BOARD zz 1\n"),
        ("GOND a 10 20 3\nLINE g 100 200 3\n", "0 BOARD a 1\n"),
        ("GOND a 10 20 3\nLINE g 100 200 3\nROUTE a g\n", "0 BOARD a 0\n"),
        ("GOND a 10 20 3\nLINE g 100 200 3\nROUTE a g\n", "0 BOARD a\n"),
        ("GOND a -1 20 3\nLINE g 100 200 3\nROUTE a g\n", "0 BOARD a 1\n"),
        ("GOND a 10 20 3\nLINE g 100 200 3 -5\nROUTE a g\n", "0 BOARD a 1\n"),
        ("BOGUS a 10 20 3\n", "0 BOARD a 1\n"),
    ],
)
def test_invalid_inputs_exit_nonzero_with_no_stdout(cfg, ev):
    """Structurally invalid inputs (including a negative standby pool) cause a
    nonzero exit and no ledger on standard output."""
    rc, out, err = run(cfg, ev)
    assert rc != 0, f"expected nonzero exit; out={out!r}"
    assert out == "", f"expected no stdout on error; got {out!r}"
    assert err.strip() != "", "expected a diagnostic on standard error"


@pytest.mark.parametrize(
    "cfg,label",
    [
        ("GOND a 10 20 3\nGOND a 5 9 2\nLINE g 100 200 3\nROUTE a g\n", "duplicate GOND"),
        ("GOND a 10 20 3\nLINE g 100 200 3\nLINE g 50 60 1\nROUTE a g\n", "duplicate LINE"),
        ("GOND a 10 20 3\nLINE g 100 200 3\nROUTE a g\nROUTE a g\n", "duplicate ROUTE"),
    ],
    ids=["dup_gond", "dup_line", "dup_route"],
)
def test_duplicate_definitions_are_rejected(cfg, label):
    """A gondola, line, or route defined twice is a structural error: the tool
    must exit nonzero with a diagnostic and emit no ledger, rather than letting a
    later definition silently override an earlier one."""
    rc, out, err = run(cfg, "0 BOARD a 1\n")
    assert rc != 0, f"{label} must be rejected; out={out!r}"
    assert out == "", f"{label} must emit no ledger; got {out!r}"
    assert err.strip() != "", f"{label} must report a diagnostic on standard error"


# ---------------------------------------------------------------------------
# Static differential corpus: a fixed set of scenarios with pre-computed
# expected ledgers, generated offline from the independent reference reducer in
# solution/reference_ledger.py. The verifier never runs a solver of its own; it
# only replays each scenario through report.py and compares the emitted ledger
# to the stored expectation.
# ---------------------------------------------------------------------------
_CORPUS_PATH = os.path.join(os.path.dirname(__file__), "differential_corpus.json")
with open(_CORPUS_PATH) as _fh:
    _DIFFERENTIAL_CORPUS = json.load(_fh)


@pytest.mark.parametrize(
    "case",
    _DIFFERENTIAL_CORPUS,
    ids=[f"corpus{i}" for i in range(len(_DIFFERENTIAL_CORPUS))],
)
def test_differential_against_stored_corpus(case):
    """Each stored scenario: report.py's ledger must equal the pre-computed
    expectation line for line, exercising the surge lifecycle, the gondola/line
    conjunction, standby-pool borrowing, the LIFO refund unwind, and the
    canonical output ordering together."""
    cfg_text, ev_text, expected = case["cfg"], case["ev"], case["expected"]
    rc, out, err = run(cfg_text, ev_text)
    assert rc == 0, (
        f"nonzero exit on valid scenario; stderr={err!r}\n"
        f"cfg={cfg_text!r}\nev={ev_text!r}"
    )
    assert out.splitlines() == expected, (
        f"ledger mismatch\ncfg={cfg_text!r}\nev={ev_text!r}\n"
        f"got={out.splitlines()!r}\nwant={expected!r}"
    )
