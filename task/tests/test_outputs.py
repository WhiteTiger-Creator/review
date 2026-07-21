"""Behavioral verifier for the arena completion-ring simulator."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

import pytest

OUT = Path("/app/output/report.json")
BIN = Path("/usr/local/bin/arena")
ARENA = "/usr/local/bin/arena"
JOURNAL = Path("/app/run/state.bin")

REQUIRED_SYMBOLS = (
    "tb_rt_run",
    "tb_ingest_tick",
    "tb_settle_tick",
    "tb_merge_drain",
    "tb_nudge_drain",
    "tb_link_detach",
    "tb_link_attach",
    "journal_load_last",
    "journal_append_stamp",
)

SCENARIOS = ("basic", "stress", "stress2")
PROFILES = ("burst", "steady")
ORDERS = ("a_then_b", "b_then_a")


def _build() -> None:
    subprocess.run(["make", "-C", "/app"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    binary = BIN.read_bytes()
    assert binary[:4] == b"\x7fELF", "expected /usr/local/bin/arena to be an ELF binary"
    assert BIN.stat().st_size > 15_000, "binary is unexpectedly small"
    nm = subprocess.run(["nm", str(BIN)], capture_output=True, text=True, check=True)
    for sym in REQUIRED_SYMBOLS:
        assert sym in nm.stdout, f"missing symbol {sym} - simulation pipeline bypassed"


@pytest.fixture(scope="module", autouse=True)
def _built_once() -> None:
    _build()


def _expected_submit_count(scenario: str, profile: str) -> int:
    """Verifier-only totals mirroring profile.c/script.c (not agent-visible)."""
    ticks = {"basic": 40, "stress": 80, "stress2": 110}[scenario]
    total = 0
    for tick in range(ticks):
        if profile == "burst":
            total += 3 if tick < 10 else (2 if tick < 20 else 1)
        elif profile == "steady":
            total += 1 if (tick % 3) == 0 else 0
        else:
            raise AssertionError(f"unknown profile: {profile}")
    return total


def _run(
    scenario: str,
    profile: str,
    order: str,
    *,
    seed: int | None = None,
    out: Path | None = None,
) -> dict:
    target = out or OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    if seed is None:
        subprocess.run(
            [ARENA, "--scenario", scenario, "--profile", profile, "--order", order, "--out", str(target)],
            check=True,
        )
    else:
        subprocess.run(
            [
                ARENA,
                "--scenario",
                scenario,
                "--profile",
                profile,
                "--order",
                order,
                "--out",
                str(target),
                "--seed",
                str(seed),
            ],
            check=True,
        )
    data = json.loads(target.read_text())
    assert set(data.keys()) == {"scenario", "profile", "events"}
    assert data["scenario"] == scenario
    assert data["profile"] == profile
    assert isinstance(data["events"], list)
    return data


def _run_expect_fail(argv: list[str], *, code: int = 2) -> None:
    result = subprocess.run([str(BIN), *argv], capture_output=True)
    assert result.returncode == code, (
        f"expected exit {code}, got {result.returncode}; stderr={result.stderr.decode(errors='replace')!r}"
    )


def _analyze(events: list[dict]) -> tuple[list[int], list[int], list[int]]:
    submitted: list[int] = []
    completes: list[int] = []
    notifies: list[int] = []
    for ev in events:
        assert set(ev.keys()) == {"kind", "id"}
        assert ev["kind"] in ("submit", "complete", "notify")
        assert isinstance(ev["id"], int)
        if ev["kind"] == "submit":
            submitted.append(ev["id"])
        elif ev["kind"] == "complete":
            completes.append(ev["id"])
        else:
            notifies.append(ev["id"])
    return submitted, completes, notifies


def _first_seen(events: list[dict]) -> dict[tuple[str, int], int]:
    first_seen: dict[tuple[str, int], int] = {}
    for index, ev in enumerate(events):
        first_seen.setdefault((ev["kind"], ev["id"]), index)
    return first_seen


def _event_sequence(data: dict) -> list[tuple[str, int]]:
    return [(ev["kind"], ev["id"]) for ev in data["events"]]


def _sequence_key(data: dict) -> tuple[tuple[str, int], ...]:
    return tuple(_event_sequence(data))


def _assert_submit_stream_monotonic(events: list[dict]) -> None:
    """Submit ids must appear as 1..N in log order (catches cursor/gen reuse)."""
    submit_ids = [ev["id"] for ev in events if ev["kind"] == "submit"]
    assert submit_ids == list(range(1, len(submit_ids) + 1)), (
        "submit ids must be strictly consecutive in emission order starting at 1"
    )


def _assert_event_triple_count(data: dict) -> None:
    submitted, completes, notifies = _analyze(data["events"])
    n = len(submitted)
    assert len(data["events"]) == 3 * n, "event log length must be exactly three events per submit"
    assert len(completes) == n and len(notifies) == n


def _assert_unique_kind_id_pairs(events: list[dict]) -> None:
    counts = Counter((ev["kind"], ev["id"]) for ev in events)
    dupes = {pair: c for pair, c in counts.items() if c > 1}
    assert dupes == {}, f"duplicate (kind,id) pairs in log: {dupes}"


def _assert_prefix_ledger(events: list[dict]) -> None:
    """At every prefix, per-id submit/complete/notify counts stay consistent."""
    submit_c: Counter[int] = Counter()
    complete_c: Counter[int] = Counter()
    notify_c: Counter[int] = Counter()
    for ev in events:
        rid = ev["id"]
        if ev["kind"] == "submit":
            submit_c[rid] += 1
            assert submit_c[rid] == 1, f"id {rid}: duplicate submit in prefix"
        elif ev["kind"] == "complete":
            complete_c[rid] += 1
            assert submit_c[rid] >= complete_c[rid], f"id {rid}: complete before submit"
            assert complete_c[rid] == 1, f"id {rid}: duplicate complete in prefix"
        else:
            notify_c[rid] += 1
            assert complete_c[rid] >= notify_c[rid], f"id {rid}: notify before complete"
            assert notify_c[rid] == 1, f"id {rid}: duplicate notify in prefix"


def _assert_simulation_shape(data: dict) -> None:
    events = data["events"]
    submitted, _, _ = _analyze(events)
    first_seen = _first_seen(events)

    submit_to_complete_gaps = [
        first_seen[("complete", request_id)] - first_seen[("submit", request_id)] for request_id in submitted
    ]
    assert len(set(submit_to_complete_gaps)) >= 3, (
        "submit→complete delays are too uniform; output looks synthesized rather than tick-simulated"
    )
    assert max(submit_to_complete_gaps) >= 3, (
        "no submit→complete delay far enough apart for multi-tick simulation"
    )

    kinds = [ev["kind"] for ev in events]
    transitions = sum(1 for left, right in zip(kinds, kinds[1:], strict=False) if left != right)
    assert transitions > len(kinds) // 2, "events are too monotonically batched for a tick-driven simulator"

    assert any(
        first_seen[("submit", left_id)] < first_seen[("complete", right_id)]
        for left_id in submitted
        for right_id in submitted
        if left_id != right_id
    ), "every completion appears before later submits; end-of-run synthesis suspected"


def _assert_notify_near_complete(events: list[dict], *, max_gap: int = 8) -> None:
    """Notify should follow complete soon after (catches detached-queue replay dumps)."""
    first_seen = _first_seen(events)
    for ev in events:
        if ev["kind"] != "notify":
            continue
        rid = ev["id"]
        gap = first_seen[("notify", rid)] - first_seen[("complete", rid)]
        assert 0 < gap <= max_gap, f"id {rid}: notify too far from complete (gap={gap})"


def _assert_exactly_once_and_notify(data: dict) -> None:
    submitted, completes, notifies = _analyze(data["events"])

    expected_n = _expected_submit_count(data["scenario"], data["profile"])
    assert len(submitted) == expected_n, "submit count must match full-tick profile (including detach windows)"

    assert len(set(submitted)) == len(submitted), "submit ids must be unique"
    assert min(submitted) == 1, "submit ids should start at 1"
    assert max(submitted) == expected_n, "submit ids should be contiguous through the final id"

    assert len(completes) == len(submitted), "must complete every submitted id exactly once"
    assert set(completes) == set(submitted), "completed set must equal submitted set"
    assert len(set(completes)) == len(completes), "no duplicate completions"

    assert len(notifies) == len(completes), "notify count must match completion count"
    assert set(notifies) == set(completes), "notify ids must match completion ids"

    first_seen = _first_seen(data["events"])
    for request_id in submitted:
        assert first_seen[("submit", request_id)] < first_seen[("complete", request_id)], (
            f"id {request_id}: submit must precede complete in the log"
        )
        assert first_seen[("complete", request_id)] < first_seen[("notify", request_id)], (
            f"id {request_id}: complete must precede notify in the log"
        )

    _assert_submit_stream_monotonic(data["events"])
    _assert_event_triple_count(data)
    _assert_unique_kind_id_pairs(data["events"])
    _assert_prefix_ledger(data["events"])
    _assert_simulation_shape(data)
    _assert_notify_near_complete(data["events"])


def _assert_full_contract(data: dict) -> None:
    _assert_exactly_once_and_notify(data)


# --- Original core matrix (strengthened) ---


def test_exactly_once_basic() -> None:
    """No detach/reattach: unique submits, exactly-once completions, 1:1 notifications."""
    data = _run("basic", "burst", "a_then_b")
    _assert_full_contract(data)


def test_exactly_once_with_reattach() -> None:
    """Single detach/reattach mid-flight: counts and per-id ordering still hold."""
    data = _run("stress", "burst", "a_then_b")
    _assert_full_contract(data)


def test_no_spurious_notifications() -> None:
    """Under reconnect stress: notifications match completions exactly."""
    data = _run("stress", "steady", "a_then_b")
    _assert_full_contract(data)


def test_multiple_reattaches() -> None:
    """Two detach/reattach cycles: invariants still hold."""
    data = _run("stress2", "steady", "a_then_b")
    _assert_full_contract(data)


def test_two_load_profiles() -> None:
    """Both burst and steady profiles satisfy invariants under reconnect."""
    burst = _run("stress", "burst", "a_then_b")
    steady = _run("stress", "steady", "a_then_b")
    _assert_full_contract(burst)
    _assert_full_contract(steady)
    assert _expected_submit_count("stress", "burst") != _expected_submit_count("stress", "steady")


def test_reconciliation_order_invariance() -> None:
    """Drain order must not change id multisets; burst runs must produce different sequences."""
    steady_a = _run("stress", "steady", "a_then_b")
    steady_b = _run("stress", "steady", "b_then_a")
    _assert_full_contract(steady_a)
    _assert_full_contract(steady_b)

    s1, c1, n1 = _analyze(steady_a["events"])
    s2, c2, n2 = _analyze(steady_b["events"])
    assert set(s1) == set(s2)
    assert set(c1) == set(c2)
    assert set(n1) == set(n2)

    burst_a = _run("stress", "burst", "a_then_b")
    burst_b = _run("stress", "burst", "b_then_a")
    _assert_full_contract(burst_a)
    _assert_full_contract(burst_b)

    assert _event_sequence(burst_a) != _event_sequence(burst_b), (
        "order flag must change the emitted event sequence for burst stress"
    )


# --- Determinism, anti-hardcoding, cross-scenario ---


def test_deterministic_rerun_identical_sequence() -> None:
    """Identical flags must yield byte-identical event sequences (no random replay)."""
    first = _run("stress2", "burst", "b_then_a", seed=17)
    second = _run("stress2", "burst", "b_then_a", seed=17)
    assert _sequence_key(first) == _sequence_key(second)
    assert _event_sequence(first) == _event_sequence(second)


def test_distinct_scenarios_do_not_share_canned_log() -> None:
    """Anti-hardcoding: basic vs stress2 logs must differ materially."""
    basic = _run("basic", "steady", "a_then_b")
    heavy = _run("stress2", "steady", "a_then_b")
    _assert_full_contract(basic)
    _assert_full_contract(heavy)
    assert _sequence_key(basic) != _sequence_key(heavy)
    assert _expected_submit_count("basic", "steady") < _expected_submit_count("stress2", "steady")


def test_distinct_profiles_change_sequence_under_same_scenario() -> None:
    """Anti-hardcoding: profile choice must change the emitted sequence, not just metadata."""
    burst = _run("stress", "burst", "a_then_b")
    steady = _run("stress", "steady", "a_then_b")
    assert burst["profile"] != steady["profile"]
    assert _sequence_key(burst) != _sequence_key(steady)


def test_stress2_volume_exceeds_stress_for_burst() -> None:
    """Larger scenario must admit strictly more submits for the same profile."""
    stress_n = _expected_submit_count("stress", "burst")
    stress2_n = _expected_submit_count("stress2", "burst")
    assert stress2_n > stress_n
    data = _run("stress2", "burst", "a_then_b")
    _assert_full_contract(data)
    assert len([ev for ev in data["events"] if ev["kind"] == "submit"]) == stress2_n


# --- Double detach, order stress, sparse/dense profiles ---


def test_stress2_burst_orders_emit_distinct_sequences() -> None:
    """Two detach windows plus burst load: order must reorder observable events."""
    a = _run("stress2", "burst", "a_then_b")
    b = _run("stress2", "burst", "b_then_a")
    _assert_full_contract(a)
    _assert_full_contract(b)
    assert _event_sequence(a) != _event_sequence(b)


def test_stress2_steady_double_detach_contract() -> None:
    """Two detach cycles on the longest scenario with sparse steady load."""
    data = _run("stress2", "steady", "b_then_a")
    _assert_full_contract(data)


def test_basic_steady_sparse_submit_pattern() -> None:
    """Steady profile only submits every third tick on the short scenario."""
    data = _run("basic", "steady", "a_then_b")
    _assert_full_contract(data)
    assert _expected_submit_count("basic", "steady") == len([ev for ev in data["events"] if ev["kind"] == "submit"])


def test_burst_early_window_submit_density() -> None:
    """Burst profile front-loads submits; early submit ids must dominate the head of the log."""
    data = _run("stress", "burst", "a_then_b")
    _assert_full_contract(data)
    submit_ids = [ev["id"] for ev in data["events"] if ev["kind"] == "submit"]
    first_third = max(1, len(submit_ids) // 3)
    assert max(submit_ids[:first_third]) >= 15, "burst profile should front-load many early submits"


def test_basic_orders_preserve_multiset_but_may_reorder() -> None:
    """Even on basic, drain order must not change id coverage."""
    a = _run("basic", "burst", "a_then_b")
    b = _run("basic", "burst", "b_then_a")
    _assert_full_contract(a)
    _assert_full_contract(b)
    assert {ev["id"] for ev in a["events"]} == {ev["id"] for ev in b["events"]}


# --- Ledger / notify placement / interleaving ---


def test_prefix_ledger_holds_on_stress_burst() -> None:
    """Explicit prefix walk on a reconnect scenario."""
    data = _run("stress", "burst", "a_then_b")
    _assert_prefix_ledger(data["events"])


def test_notify_complete_gap_bounded_under_double_detach() -> None:
    """Notifies must land soon after completes even with two journal generations."""
    data = _run("stress2", "burst", "a_then_b")
    _assert_full_contract(data)
    _assert_notify_near_complete(data["events"], max_gap=10)


def test_no_notify_before_any_complete_in_global_log() -> None:
    """Global ordering: first notify index must follow at least one complete."""
    data = _run("stress", "steady", "b_then_a")
    events = data["events"]
    first_complete = next(i for i, ev in enumerate(events) if ev["kind"] == "complete")
    first_notify = next(i for i, ev in enumerate(events) if ev["kind"] == "notify")
    assert first_notify > first_complete


def test_interleaved_submit_and_complete_across_ids() -> None:
    """Reject terminal batch synthesis: work continues while earlier ids complete."""
    data = _run("stress2", "burst", "b_then_a")
    _assert_full_contract(data)
    first_seen = _first_seen(data["events"])
    submitted = [ev["id"] for ev in data["events"] if ev["kind"] == "submit"]
    assert any(
        first_seen[("submit", hi)] > first_seen[("complete", lo)]
        for lo in submitted
        for hi in submitted
        if hi > lo
    ), "expected overlap between later submits and earlier completions"


def test_stress_detach_window_ids_still_notify_after_reattach() -> None:
    """Ids whose work spans detach must still receive exactly one notify."""
    data = _run("stress", "burst", "a_then_b")
    _assert_full_contract(data)
    # stress detach ticks 22..31 — with burst, many ids are minted before and during window.
    mid_ids = range(20, 45)
    notifies = {ev["id"] for ev in data["events"] if ev["kind"] == "notify"}
    submits = {ev["id"] for ev in data["events"] if ev["kind"] == "submit"}
    touched = [i for i in mid_ids if i in submits]
    assert touched, "expected submits in the detach window band"
    assert all(i in notifies for i in touched), "detach-window submits must still notify exactly once"


# --- Matrix sweep (regression grid) ---


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("profile", PROFILES)
def test_matrix_exactly_once_contract(scenario: str, profile: str) -> None:
    """Full 3x2 scenario/profile grid must satisfy the contract under default order."""
    data = _run(scenario, profile, "a_then_b")
    _assert_full_contract(data)


@pytest.mark.parametrize("order", ORDERS)
def test_stress_burst_respects_order_flag(order: str) -> None:
    """Both reconciliation orders must yield valid logs for burst reconnect stress."""
    data = _run("stress", "burst", order)
    _assert_full_contract(data)


# --- CLI / malformed invocation ---


def test_invalid_scenario_rejected() -> None:
    """Unknown scenario must fail fast instead of writing a report."""
    bad_out = OUT.with_name("invalid.json")
    if bad_out.exists():
        bad_out.unlink()
    _run_expect_fail(
        [ARENA, "--scenario", "bogus", "--profile", "burst", "--order", "a_then_b", "--out", str(bad_out)],
        code=2,
    )


def test_missing_required_flag_rejected() -> None:
    """Incomplete CLI must not silently succeed."""
    _run_expect_fail([ARENA, "--scenario", "basic", "--profile", "burst"], code=2)


def test_invalid_order_rejected() -> None:
    """Unknown reconciliation order must not produce output."""
    _run_expect_fail(
        [ARENA, "--scenario", "basic", "--profile", "burst", "--order", "z_then_y", "--out", str(OUT)],
        code=2,
    )


# --- Anti static-output / rebuild coupling ---


def test_output_removed_between_runs() -> None:
    """Verifier pattern deletes prior JSON; agent cannot rely on a stale file."""
    alt = OUT.with_name("report_alt.json")
    first = _run("basic", "burst", "a_then_b", out=alt)
    assert alt.exists()
    second = _run("basic", "burst", "a_then_b")
    assert _sequence_key(first) == _sequence_key(second)
    _assert_full_contract(second)


def test_journal_file_created_on_detach_scenario() -> None:
    """Detach scenarios must persist stamps (journal grows); catches no-op link/journal fixes."""
    if JOURNAL.exists():
        JOURNAL.unlink()
    _run("stress2", "burst", "a_then_b")
    assert JOURNAL.exists(), "expected detach scenario to write journal stamps"
    # Each stamp is gen (u32) + cursor (u64) => 12 bytes; stress2 performs two detach cycles.
    assert JOURNAL.stat().st_size >= 24, "journal should contain a stamp per detach"


def test_high_gen_token_path_stress2_burst() -> None:
    """Long burst run after reattach bumps generation — catches truncated token/journal keys."""
    data = _run("stress2", "burst", "b_then_a")
    _assert_full_contract(data)
    assert max(ev["id"] for ev in data["events"]) == _expected_submit_count("stress2", "burst")


def test_completes_not_clustered_in_final_fifth() -> None:
    """Reject implementations that defer all completions to the post-loop drain only."""
    data = _run("stress", "burst", "a_then_b")
    events = data["events"]
    completes = [i for i, ev in enumerate(events) if ev["kind"] == "complete"]
    cutoff = int(len(events) * 0.8)
    early = [i for i in completes if i < cutoff]
    assert len(early) >= len(completes) // 2, "most completions should appear before the final 20% of the log"
