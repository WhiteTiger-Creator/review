import os
import hmac
import json
import hashlib
import requests
import pytest

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8780")
LOG_SECRET = os.environ.get("LOG_SECRET") or "crop_plan_l0g_2026"
SEEDS = [10, 30, 50, 70, 90]
EVAL_BUDGET_PER_SEED = 10
GLOBAL_EVAL_CAP = 45
MIN_DISTINCT_EVALS = 4
MIN_WINS = 3
MIN_STRONG_WINS = 2


@pytest.fixture(scope="session")
def event_journal():
    """Load the full server event history once for all assertions."""
    resp = requests.get(f"{BASE_URL}/events", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    return data


def has_valid_signature(event):
    """Return True when an event carries the expected HMAC digest."""
    raw_entry = {"type": event["type"], "data": event["data"]}
    raw = json.dumps(raw_entry, sort_keys=True)
    expected = hmac.HMAC(LOG_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]
    return hmac.compare_digest(expected, event.get("sig", ""))


def test_result_summary_file_has_seed_entries():
    """The results report must exist, be non-empty, and mention every required seed."""
    assert os.path.isfile("/app/output/result.txt"), "Missing /app/output/result.txt"
    with open("/app/output/result.txt") as f:
        content = f.read().strip()
    assert len(content) > 0, "result.txt is empty"
    for seed in SEEDS:
        assert str(seed) in content, f"Seed {seed} not mentioned in result.txt"


def test_audit_json_matches_finish_outcomes(event_journal):
    """Structured audit output must mirror each finish event with required keys."""
    assert os.path.isfile("/app/output/audit.json"), "Missing /app/output/audit.json"
    with open("/app/output/audit.json") as f:
        audit_rows = json.load(f)
    assert isinstance(audit_rows, list), "audit.json must be a JSON array"
    assert len(audit_rows) == len(SEEDS), f"Expected {len(SEEDS)} audit rows"
    finish_by_seed = {
        ev["data"]["seed"]: ev["data"]
        for ev in event_journal["events"]
        if ev["type"] == "finish"
    }
    for row in audit_rows:
        for key in ("seed", "assignment", "true_score", "threshold", "won"):
            assert key in row, f"audit row missing key {key}"
        finish = finish_by_seed[row["seed"]]
        assert row["assignment"] == finish["assignment"]
        assert row["true_score"] == finish["true_score"]
        assert row["threshold"] == finish["threshold"]
        assert row["won"] == finish["won"]


def test_game_initialization_count_is_exact(event_journal):
    """Exactly one game start should be recorded for each required seed."""
    new_games = [ev for ev in event_journal["events"] if ev["type"] == "new_game"]
    assert len(new_games) == 5, f"Expected 5 new_game events, got {len(new_games)}"


def test_final_submission_count_is_exact(event_journal):
    """Exactly one final submission should be present per seed."""
    finishes = [ev for ev in event_journal["events"] if ev["type"] == "finish"]
    assert len(finishes) == 5, f"Expected 5 finish events, got {len(finishes)}"


def test_every_required_seed_has_a_finish_event(event_journal):
    """All mandated seeds must appear in the recorded finish events."""
    finish_seeds = {ev["data"]["seed"] for ev in event_journal["events"] if ev["type"] == "finish"}
    for seed in SEEDS:
        assert seed in finish_seeds, f"Seed {seed} was not played"


def test_win_quota_meets_majority_requirement(event_journal):
    """At least three of the five seeds must beat the 80th-percentile threshold."""
    finishes = [ev for ev in event_journal["events"] if ev["type"] == "finish"]
    wins = sum(1 for ev in finishes if ev["data"].get("won"))
    assert wins >= MIN_WINS, f"Won {wins}/5 seeds, need at least {MIN_WINS}"


def test_global_evaluation_cap_not_exceeded(event_journal):
    """Total evaluation slot spend across the run must stay within the global cap."""
    total_cost = 0
    for ev in event_journal["events"]:
        if ev["type"] == "evaluate":
            total_cost += ev["data"].get("eval_cost", 1)
    assert total_cost <= GLOBAL_EVAL_CAP, (
        f"Used {total_cost} global eval slots, cap is {GLOBAL_EVAL_CAP}"
    )
    assert event_journal.get("global_evals_used", total_cost) <= GLOBAL_EVAL_CAP


def test_per_seed_evaluation_budget_not_exceeded(event_journal):
    """No seed may exceed ten evaluation slots including duplicate penalties."""
    eval_cost_per_seed = {}
    for ev in event_journal["events"]:
        if ev["type"] == "evaluate":
            seed = ev["data"]["seed"]
            cost = ev["data"].get("eval_cost", 1)
            eval_cost_per_seed[seed] = eval_cost_per_seed.get(seed, 0) + cost
    for seed, spent in eval_cost_per_seed.items():
        assert spent <= EVAL_BUDGET_PER_SEED, (
            f"Seed {seed} used {spent} eval slots, max is {EVAL_BUDGET_PER_SEED}"
        )


def test_no_rejected_game_starts(event_journal):
    """Duplicate /new_game attempts must not appear in the persistent event log."""
    rejected = [ev for ev in event_journal["events"] if ev["type"] == "new_game_rejected"]
    assert len(rejected) == 0, (
        f"Found {len(rejected)} rejected duplicate game starts; "
        "each seed may be started only once for the whole run"
    )


def test_each_seed_started_at_most_once(event_journal):
    """Every seed may appear in at most one successful new_game event."""
    starts_per_seed = {}
    for ev in event_journal["events"]:
        if ev["type"] == "new_game":
            seed = ev["data"]["seed"]
            starts_per_seed[seed] = starts_per_seed.get(seed, 0) + 1
    for seed, count in starts_per_seed.items():
        assert count == 1, f"Seed {seed} started {count} times, expected exactly 1"


def test_field_notes_requested_for_every_seed(event_journal):
    """Each started seed must have at least one field_notes lookup in the journal."""
    noted = {ev["data"]["seed"] for ev in event_journal["events"] if ev["type"] == "field_notes"}
    for seed in SEEDS:
        assert seed in noted, f"Seed {seed} missing field_notes event"


def test_logged_events_use_valid_signatures(event_journal):
    """Each event must include a correct signature so logs cannot be forged."""
    events = event_journal["events"]
    assert len(events) > 0, "No events logged"
    for ev in events:
        assert has_valid_signature(ev), f"Invalid signature on event: {ev['type']}"


def test_each_seed_has_required_exploration_diversity(event_journal):
    """Each seed needs four distinct evaluated assignments before finish."""
    for seed in SEEDS:
        eval_events = [
            ev for ev in event_journal["events"]
            if ev["type"] == "evaluate" and ev["data"]["seed"] == seed
        ]
        distinct_configs = set()
        for ev in eval_events:
            assignment = ev["data"].get("assignment", [])
            distinct_configs.add(tuple(assignment))
        assert len(distinct_configs) >= MIN_DISTINCT_EVALS, (
            f"Seed {seed}: only {len(distinct_configs)} distinct assignments, "
            f"need at least {MIN_DISTINCT_EVALS}"
        )


def test_finished_assignment_was_previously_evaluated(event_journal):
    """A finish submission must reuse one of that seed's evaluated assignments."""
    for seed in SEEDS:
        finish_events = [
            ev for ev in event_journal["events"]
            if ev["type"] == "finish" and ev["data"]["seed"] == seed
        ]
        assert len(finish_events) == 1, (
            f"Seed {seed}: expected 1 finish event, got {len(finish_events)}"
        )
        submitted = tuple(finish_events[0]["data"].get("assignment", []))
        eval_events = [
            ev for ev in event_journal["events"]
            if ev["type"] == "evaluate" and ev["data"]["seed"] == seed
        ]
        tested_configs = {tuple(ev["data"].get("assignment", [])) for ev in eval_events}
        assert submitted in tested_configs, (
            f"Seed {seed}: submitted assignment was not among evaluated configurations"
        )


def test_finished_assignment_had_highest_noisy_score(event_journal):
    """Each finish must submit the evaluated assignment with the top noisy_score."""
    for seed in SEEDS:
        eval_events = [
            ev for ev in event_journal["events"]
            if ev["type"] == "evaluate" and ev["data"]["seed"] == seed
        ]
        assert eval_events, f"Seed {seed}: no evaluate events recorded"
        best_noisy = max(ev["data"]["noisy_score"] for ev in eval_events)
        best_assignments = {
            tuple(ev["data"].get("assignment", []))
            for ev in eval_events
            if ev["data"]["noisy_score"] == best_noisy
        }
        finish_events = [
            ev for ev in event_journal["events"]
            if ev["type"] == "finish" and ev["data"]["seed"] == seed
        ]
        submitted = tuple(finish_events[0]["data"].get("assignment", []))
        assert submitted in best_assignments, (
            f"Seed {seed}: finish assignment did not match highest noisy_score "
            f"({best_noisy}); candidates {sorted(best_assignments)}, got {submitted}"
        )


def test_at_least_two_wins_have_clear_margin(event_journal):
    """At least two winning seeds must beat threshold by two or more points."""
    finishes = [ev for ev in event_journal["events"] if ev["type"] == "finish"]
    strong_wins = 0
    for ev in finishes:
        if ev["data"].get("won"):
            margin = ev["data"]["true_score"] - ev["data"]["threshold"]
            if margin >= 2:
                strong_wins += 1
    assert strong_wins >= MIN_STRONG_WINS, (
        f"Only {strong_wins} wins had margin >= 2, need at least {MIN_STRONG_WINS}"
    )


def test_server_source_not_exposed_in_agent_workspace():
    """Scoring implementation must not be present in the agent workspace."""
    assert not os.path.isfile("/app/server.py"), (
        "server.py must not be shipped under /app"
    )


def test_planner_secrets_are_locked_down():
    """Secrets file must be root-only so non-root agents cannot read scoring keys."""
    secrets_path = "/etc/crop-planner/env"
    assert os.path.isfile(secrets_path), "Missing /etc/crop-planner/env"
    mode = os.stat(secrets_path).st_mode & 0o777
    assert mode == 0o400, f"/etc/crop-planner/env mode {oct(mode)}, expected 0400"


def test_server_implementation_not_world_readable():
    """Server source must be group-gated and absent from /app."""
    server_path = "/opt/crop-planner/server.py"
    assert os.path.isfile(server_path), "Missing /opt/crop-planner/server.py"
    mode = os.stat(server_path).st_mode & 0o777
    assert mode & 0o004 == 0, f"{server_path} is world-readable (mode {oct(mode)})"
    assert mode & 0o077 in (0o070, 0o050), (
        f"{server_path} must be group-only (mode {oct(mode)})"
    )
