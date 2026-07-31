"""Behavioral check for the restored snapshot reclaim supervisor.

Every rule graded here is written in /app/PROTOCOL.md and exhibited by a worked
sample under /app/samples/. The suite replays those samples and then feeds a
held-out population of pools built from a fixed seed at grading time. A pool is
compared whole, both digests included, so a supervisor that gets one rule wrong
scores zero on every pool that rule touches.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _sibling(name: str):
    """Load a helper module beside this file without touching sys.path.

    Each module is registered under its own name first, so a helper that
    imports another helper resolves it here rather than from the interpreter's
    search path.
    """
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


reference = _sibling("reference")
generate = _sibling("generate")

APP = Path(os.environ.get("RECLAIM_APP", "/app"))
BIN = APP / "reclaim"
SAMPLES = APP / "samples"


@pytest.fixture(scope="session", autouse=True)
def built_binary() -> None:
    """The submitted sources compile cleanly into the operator command."""
    proc = subprocess.run(
        ["go", "build", "-o", str(BIN), "./cmd/reclaim"],
        cwd=APP, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr


def run_plan(tmp_path: Path, pools: list[dict], name: str = "pools.jsonl"):
    src = tmp_path / name
    src.write_text("".join(json.dumps(pool, separators=(",", ":")) + "\n" for pool in pools))
    out = tmp_path / "report.json"
    proc = subprocess.run(
        [str(BIN), "plan", "--pools", str(src), "--out", str(out)],
        capture_output=True, text=True, check=False,
    )
    report = json.loads(out.read_text()) if out.exists() else None
    return proc, report


@pytest.fixture(scope="session")
def graded(tmp_path_factory) -> dict:
    """One run over the whole held-out population, reused by the pool checks."""
    pools = generate.graded_pools()
    proc, report = run_plan(tmp_path_factory.mktemp("graded"), pools)
    return {"proc": proc, "report": report, "pools": pools,
            "expected": reference.plan(pools)}


def sample_dirs() -> list[Path]:
    return sorted(p for p in SAMPLES.iterdir() if p.is_dir())


def pool_row(report: dict, name: str) -> dict | None:
    for row in report.get("pools", []):
        if row.get("pool") == name:
            return row
    return None


# --- the recorded samples -------------------------------------------------


@pytest.mark.parametrize("sample", sample_dirs(), ids=lambda p: p.name)
def test_reproduces_recorded_sample(tmp_path: Path, sample: Path) -> None:
    """Each worked sample comes back exactly as the supervisor reported it.

    Expected values are recomputed here from the sample's own record, so the
    shipped report is graded rather than trusted.
    """
    pools = [json.loads(row) for row in (sample / "pools.jsonl").read_text().splitlines() if row.strip()]
    expected = reference.plan(pools)
    assert json.loads((sample / "report.json").read_text()) == expected, \
        f"{sample.name} was modified in the image"
    proc, report = run_plan(tmp_path, pools)
    assert proc.returncode == 0, proc.stderr
    assert report == expected


# --- the held-out population ----------------------------------------------


def test_graded_run_succeeds(graded: dict) -> None:
    """The supervisor accepts the held-out population and writes a report."""
    assert graded["proc"].returncode == 0, graded["proc"].stderr
    assert graded["report"] is not None


@pytest.mark.parametrize("name", [f"pool{index:02d}" for index in range(generate.COUNT)])
def test_heldout_pool_row_matches(graded: dict, name: str) -> None:
    """Every field of the pool row, its digest included, matches."""
    assert graded["report"] is not None, "no report was written"
    expected = pool_row(graded["expected"], name)
    assert pool_row(graded["report"], name) == expected


@pytest.mark.parametrize("name", [f"pool{index:02d}" for index in range(generate.COUNT)])
def test_heldout_pool_row_is_self_consistent(graded: dict, name: str) -> None:
    """The row agrees with itself: recomputing from what it reports reproduces it.

    The freed total is recomputed from the row's own pruned list against the
    pool's extents, and the digest is recomputed from the row's own fields, so a
    row that reports a plan and a total that do not belong together fails here
    whatever the expected values are.
    """
    assert graded["report"] is not None, "no report was written"
    row = pool_row(graded["report"], name)
    assert row is not None, f"{name} missing from the report"
    pool = next(item for item in graded["pools"] if item["pool"] == name)
    ids = [snap["id"] for snap in pool["snapshots"]]
    kept = [item["id"] for item in row["retained"]]
    assert sorted(kept + row["pruned"]) == sorted(ids)
    assert kept == [sid for sid in ids if sid in set(kept)]
    assert row["pruned"] == [sid for sid in ids if sid in set(row["pruned"])]
    surviving = {index: "kept" for index, sid in enumerate(ids) if sid in set(kept)}
    assert row["freed_blocks"] == reference.freed_blocks(pool, surviving)
    assert row["digest"] == reference.pool_digest(row)
    assert row["shortfall"] == max(0, pool["target_blocks"] - row["freed_blocks"])


def test_heldout_report_digest_matches(graded: dict) -> None:
    """The report digest seals the whole population in report order."""
    assert graded["report"] is not None, "no report was written"
    assert graded["report"]["digest"] == graded["expected"]["digest"]
    assert [row["pool"] for row in graded["report"]["pools"]] == \
        [row["pool"] for row in graded["expected"]["pools"]]


# --- named rules ----------------------------------------------------------


DROP = object()  # sentinel: remove the key entirely rather than set it to null


def base_pool(**overrides) -> dict:
    pool = {
        "pool": "unit",
        "now": "2026-03-30T00:00:00Z",
        "keep": {"hourly": 0, "daily": 1, "weekly": 0, "monthly": 0},
        "target_blocks": 0,
        "snapshots": [
            {"id": "u-00", "taken": "2026-03-23T01:00:00Z"},
            {"id": "u-01", "taken": "2026-03-23T02:00:00Z"},
            {"id": "u-02", "taken": "2026-03-27T03:00:00Z"},
        ],
        "extents": [{"blocks": 10, "first": 0, "last": 1, "live": False}],
    }
    pool.update(overrides)
    # PROTOCOL.md treats a missing keep or target_blocks as fatal, which is a
    # different input from one present and null, so a drop sentinel removes the
    # key outright rather than setting it to None.
    for key, value in list(pool.items()):
        if value is DROP:
            del pool[key]
    return pool


def test_shared_extent_needs_its_whole_span_released(tmp_path: Path) -> None:
    """An extent spanning two snapshots frees only when both are released."""
    pool = base_pool(extents=[
        {"blocks": 64, "first": 0, "last": 1, "live": False},
        {"blocks": 9, "first": 1, "last": 2, "live": False},
    ])
    proc, report = run_plan(tmp_path, [pool])
    assert proc.returncode == 0, proc.stderr
    row = pool_row(report, "unit")
    assert row["pruned"] == ["u-00", "u-01"]
    assert row["freed_blocks"] == 64


def test_live_extent_is_never_freed(tmp_path: Path) -> None:
    """An extent the current filesystem still references never counts."""
    pool = base_pool(extents=[{"blocks": 500, "first": 0, "last": 1, "live": True}])
    proc, report = run_plan(tmp_path, [pool])
    assert proc.returncode == 0, proc.stderr
    assert pool_row(report, "unit")["freed_blocks"] == 0


def test_period_representative_is_the_earliest_snapshot(tmp_path: Path) -> None:
    """The first snapshot taken in a period is the one the tier keeps."""
    pool = base_pool(keep={"hourly": 0, "daily": 2, "weekly": 0, "monthly": 0})
    proc, report = run_plan(tmp_path, [pool])
    assert proc.returncode == 0, proc.stderr
    row = pool_row(report, "unit")
    assert [item["id"] for item in row["retained"]] == ["u-00", "u-02"]
    assert row["pruned"] == ["u-01"]


def test_anchor_does_not_spend_a_keep_slot(tmp_path: Path) -> None:
    """A held or cloned representative is free, so the tier reaches further."""
    snaps = [
        {"id": "u-00", "taken": "2026-03-23T01:00:00Z"},
        {"id": "u-01", "taken": "2026-03-25T02:00:00Z"},
        {"id": "u-02", "taken": "2026-03-27T03:00:00Z", "clone": True},
    ]
    pool = base_pool(snapshots=snaps, keep={"hourly": 0, "daily": 1, "weekly": 0, "monthly": 0})
    proc, report = run_plan(tmp_path, [pool])
    assert proc.returncode == 0, proc.stderr
    row = pool_row(report, "unit")
    assert [(item["id"], item["class"]) for item in row["retained"]] == \
        [("u-01", "daily"), ("u-02", "clone")]


def test_expired_hold_is_inert(tmp_path: Path) -> None:
    """A hold at or before now has lapsed and keeps nothing."""
    snaps = [
        {"id": "u-00", "taken": "2026-03-23T01:00:00Z", "hold_until": "2026-03-24T00:00:00Z"},
        {"id": "u-01", "taken": "2026-03-25T02:00:00Z"},
        {"id": "u-02", "taken": "2026-03-27T03:00:00Z"},
    ]
    pool = base_pool(snapshots=snaps)
    proc, report = run_plan(tmp_path, [pool])
    assert proc.returncode == 0, proc.stderr
    assert pool_row(report, "unit")["pruned"] == ["u-00", "u-01"]


def test_hold_outranks_clone(tmp_path: Path) -> None:
    """One snapshot carrying both an unexpired hold and a clone reports hold."""
    snaps = [
        {"id": "u-00", "taken": "2026-03-23T01:00:00Z"},
        {"id": "u-01", "taken": "2026-03-25T02:00:00Z",
         "hold_until": "2026-06-01T00:00:00Z", "clone": True},
        {"id": "u-02", "taken": "2026-03-27T03:00:00Z"},
    ]
    pool = base_pool(snapshots=snaps, keep={"hourly": 0, "daily": 0, "weekly": 0, "monthly": 0})
    proc, report = run_plan(tmp_path, [pool])
    assert proc.returncode == 0, proc.stderr
    assert [(item["id"], item["class"]) for item in pool_row(report, "unit")["retained"]] == \
        [("u-01", "hold")]


def test_week_runs_monday_to_sunday(tmp_path: Path) -> None:
    """A Sunday belongs to the week that started the Monday before it."""
    snaps = [
        {"id": "u-00", "taken": "2026-03-19T10:00:00Z"},
        {"id": "u-01", "taken": "2026-03-22T10:00:00Z"},
        {"id": "u-02", "taken": "2026-03-23T10:00:00Z"},
    ]
    pool = base_pool(snapshots=snaps, keep={"hourly": 0, "daily": 0, "weekly": 1, "monthly": 0},
                     extents=[{"blocks": 11, "first": 0, "last": 1, "live": False}])
    proc, report = run_plan(tmp_path, [pool])
    assert proc.returncode == 0, proc.stderr
    row = pool_row(report, "unit")
    assert [item["id"] for item in row["retained"]] == ["u-02"]
    assert row["freed_blocks"] == 11


def test_class_is_the_first_tier_that_applies(tmp_path: Path) -> None:
    """Classes are tried hold, clone, hourly, daily, weekly, monthly."""
    pool = base_pool(keep={"hourly": 1, "daily": 1, "weekly": 1, "monthly": 1})
    proc, report = run_plan(tmp_path, [pool])
    assert proc.returncode == 0, proc.stderr
    row = pool_row(report, "unit")
    assert [(item["id"], item["class"]) for item in row["retained"]] == \
        [("u-00", "weekly"), ("u-02", "hourly")]


def test_ladder_relaxes_the_finest_tier_first(tmp_path: Path) -> None:
    """A short pool steps down hourly, then daily, then weekly, then monthly."""
    pool = base_pool(keep={"hourly": 2, "daily": 1, "weekly": 0, "monthly": 0},
                     target_blocks=10)
    proc, report = run_plan(tmp_path, [pool])
    assert proc.returncode == 0, proc.stderr
    row = pool_row(report, "unit")
    assert row["passes"] == 1
    assert row["keep_final"] == {"hourly": 1, "daily": 1, "weekly": 0, "monthly": 0}
    assert row["freed_blocks"] == 10


def test_freed_total_describes_the_final_set_only(tmp_path: Path) -> None:
    """The freed total is recomputed, never accumulated over the passes."""
    pool = base_pool(
        keep={"hourly": 0, "daily": 2, "weekly": 0, "monthly": 0},
        target_blocks=30,
        extents=[
            {"blocks": 20, "first": 1, "last": 1, "live": False},
            {"blocks": 20, "first": 0, "last": 0, "live": False},
        ],
    )
    proc, report = run_plan(tmp_path, [pool])
    assert proc.returncode == 0, proc.stderr
    row = pool_row(report, "unit")
    assert row["passes"] == 1
    assert row["freed_blocks"] == 40


def test_unreachable_target_reports_a_shortfall(tmp_path: Path) -> None:
    """A run that bottoms out short reports the gap it could not close."""
    pool = base_pool(target_blocks=1000)
    proc, report = run_plan(tmp_path, [pool])
    assert proc.returncode == 0, proc.stderr
    row = pool_row(report, "unit")
    assert row["retained"] == []
    assert row["freed_blocks"] == 10
    assert row["shortfall"] == 990


def test_rows_are_listed_in_taken_order(tmp_path: Path) -> None:
    """Snapshot lists follow the taken order, not the id order."""
    snaps = [
        {"id": "u-zz", "taken": "2026-03-23T01:00:00Z"},
        {"id": "u-aa", "taken": "2026-03-25T02:00:00Z"},
        {"id": "u-mm", "taken": "2026-03-27T03:00:00Z"},
    ]
    pool = base_pool(snapshots=snaps, keep={"hourly": 0, "daily": 0, "weekly": 0, "monthly": 0},
                     extents=[{"blocks": 3, "first": 0, "last": 2, "live": False}])
    proc, report = run_plan(tmp_path, [pool])
    assert proc.returncode == 0, proc.stderr
    assert pool_row(report, "unit")["pruned"] == ["u-zz", "u-aa", "u-mm"]


def test_pools_are_sorted_by_name(tmp_path: Path) -> None:
    """Report order is by pool name whatever order the records arrive in."""
    pools = [base_pool(pool="zeta"), base_pool(pool="alpha"), base_pool(pool="mid")]
    proc, report = run_plan(tmp_path, pools)
    assert proc.returncode == 0, proc.stderr
    assert [row["pool"] for row in report["pools"]] == ["alpha", "mid", "zeta"]


# --- fatal input ----------------------------------------------------------


@pytest.mark.parametrize(
    "broken",
    [
        pytest.param(base_pool(snapshots=[
            {"id": "u-00", "taken": "2026-03-23T01:00:00Z"},
            {"id": "u-00", "taken": "2026-03-25T02:00:00Z"},
            {"id": "u-02", "taken": "2026-03-27T03:00:00Z"},
        ]), id="duplicate-snapshot-id"),
        pytest.param(base_pool(snapshots=[
            {"id": "u-00", "taken": "2026-03-25T01:00:00Z"},
            {"id": "u-01", "taken": "2026-03-23T02:00:00Z"},
            {"id": "u-02", "taken": "2026-03-27T03:00:00Z"},
        ]), id="taken-not-increasing"),
        pytest.param(base_pool(extents=[{"blocks": 5, "first": 1, "last": 9, "live": False}]),
                     id="extent-index-out-of-range"),
        pytest.param(base_pool(extents=[{"blocks": 5, "first": 2, "last": 1, "live": False}]),
                     id="extent-first-after-last"),
        pytest.param(base_pool(now="2026-03-30"), id="bad-timestamp"),
        pytest.param(base_pool(keep={"hourly": -1, "daily": 1, "weekly": 0, "monthly": 0}),
                     id="negative-keep"),
        pytest.param(base_pool(snapshots=[]), id="empty-snapshots"),
        pytest.param(base_pool(keep=DROP), id="missing-keep"),
        pytest.param(base_pool(target_blocks=DROP), id="missing-target-blocks"),
        pytest.param(base_pool(extents=[{"blocks": 0, "first": 0, "last": 1, "live": False}]),
                     id="non-positive-extent-blocks"),
    ],
)
def test_fatal_input_exits_nonzero_without_output(tmp_path: Path, broken: dict) -> None:
    """A rejected record exits nonzero and leaves no report behind."""
    proc, report = run_plan(tmp_path, [broken])
    assert proc.returncode != 0
    assert report is None


def test_duplicate_pool_name_is_fatal(tmp_path: Path) -> None:
    """Two records for the same pool are a rejected input."""
    proc, report = run_plan(tmp_path, [base_pool(), base_pool()])
    assert proc.returncode != 0
    assert report is None
