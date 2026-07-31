"""Verifier for skiff hop lab."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
REPORT = APP / "output" / "skiff_report.json"
BUNDLE = APP / "data" / "bundle.json"

GRAV = 0.5
IMPULSE = -8.0
GRACE_MAX = 4
STASH_MAX = 4


def _arm_g(on: bool, grace: int, ceiling: int) -> int:
    if on:
        return ceiling
    if grace <= 0:
        return 0
    return grace - 1


def _pull_s(latch: int, pressed: bool, eligible: bool, ceiling: int) -> tuple[int, bool]:
    s = ceiling if pressed else latch
    if s <= 0:
        return 0, False
    if eligible:
        return 0, True
    return s - 1, False


def _snap(y: float, top: float, skin: float, vy: float) -> tuple[float, bool]:
    if vy >= 0 and y >= top and y <= top + skin:
        return top, True
    return y, False


def _load_case(cid: str) -> dict:
    return json.loads((APP / "data" / "cases" / cid / "case.json").read_text())


def _simulate(case: dict) -> tuple[float, int, str]:
    x = float(case["start_x"])
    y = float(case["start_y"])
    vx = float(case["vx"])
    vy = 0.0
    on = True
    grace = GRACE_MAX
    stash = 0
    hops = 0
    apex = y
    skin = float(case.get("skin") or 0.5)
    press = list(case["press"])
    solids = case["solids"]
    ticks = int(case["ticks"])

    for i in range(ticks):
        vy += GRAV
        x += vx
        y += vy
        apex = min(apex, y)
        seated = False
        for sol in solids:
            if x < float(sol["x0"]) or x > float(sol["x1"]):
                continue
            top = float(sol["y"])
            if sol.get("one_way"):
                ny, ok = _snap(y, top, skin, vy)
                if ok:
                    y = ny
                    vy = 0.0
                    seated = True
            elif y >= top:
                y = top
                if vy > 0:
                    vy = 0.0
                seated = True
        on = seated
        grace = _arm_g(on, grace, GRACE_MAX)
        eligible = on or grace > 0
        pressed = i < len(press) and press[i] != 0
        stash, hop = _pull_s(stash, pressed, eligible, STASH_MAX)
        if hop:
            vy = IMPULSE
            on = False
            grace = 0
            hops += 1

    fp = f"x{int(x * 10 + 0.5)}y{int(y * 10 + 0.5)}h{hops}"
    return apex, hops, fp


def _rebuild_and_run() -> dict:
    subprocess.run(["/app/scripts/build.sh"], check=True)
    subprocess.run(["/app/scripts/run.sh"], check=True)
    return json.loads(REPORT.read_text())


@pytest.fixture(scope="module")
def report() -> dict:
    if not REPORT.exists():
        return _rebuild_and_run()
    return json.loads(REPORT.read_text())


@pytest.fixture(scope="module")
def bundle() -> dict:
    return json.loads(BUNDLE.read_text())


def _row(report: dict, cid: str) -> dict:
    for row in report["cases"]:
        if row["id"] == cid:
            return row
    raise AssertionError(f"missing case {cid}")


def _assert_case(report: dict, cid: str) -> None:
    case = _load_case(cid)
    apex, hops, fp = _simulate(case)
    row = _row(report, cid)
    assert row["settled"] is True
    assert row["hop_count"] == hops
    assert abs(row["apex_y"] - apex) < 1e-6
    assert row["footprint"] == fp


def test_plain_ok(report):
    """Solid-floor case matches the independent reference row."""
    _assert_case(report, "plain_floor")


def test_hash_stable(report):
    """Rebuild and replay reproduce the same digest_hex."""
    again = _rebuild_and_run()
    assert again["digest_hex"] == report["digest_hex"]
    assert len(again["digest_hex"]) == 64


def test_edge_leave_ok(report):
    """Edge-leave case matches the independent reference row."""
    _assert_case(report, "edge_leave")


def test_early_press_ok(report):
    """Early press case matches the independent reference row."""
    _assert_case(report, "early_press")


def test_land_stash_ok(report):
    """Touchdown press case matches the independent reference row."""
    _assert_case(report, "land_stash")


def test_no_double_ok(report):
    """Held short-press case matches the independent reference row."""
    _assert_case(report, "no_double")


def test_rise_clear_ok(report):
    """Rise-through shelf case matches the independent reference row."""
    _assert_case(report, "rise_clear")


def test_catalog_full(report, bundle):
    """cases_passing equals the bundle catalog size with the expected schema."""
    assert report["cases_passing"] == len(bundle["cases"])
    assert report["bundle_id"] == bundle["id"]
    assert report["schema_version"] == "skiff_report_v1"


def test_plank_land_ok(report):
    """Thin-shelf landing case matches the independent reference row."""
    _assert_case(report, "plank_land")


def test_native_suite_ok():
    """Go unit suite under /app stays green."""
    subprocess.run(["/app/scripts/unit.sh"], check=True)


def test_ledger_ok(report, bundle):
    """Every bundle case appears settled in the report ledger."""
    ids = {r["id"] for r in report["cases"]}
    assert ids == set(bundle["cases"])
    assert all(r["settled"] for r in report["cases"])


def test_second_pass(report):
    """A second rebuild and replay reproduces digest_hex and reference rows."""
    again = _rebuild_and_run()
    assert again["digest_hex"] == report["digest_hex"]
    for row in again["cases"]:
        apex, hops, fp = _simulate(_load_case(row["id"]))
        assert row["hop_count"] == hops
        assert abs(row["apex_y"] - apex) < 1e-6
        assert row["footprint"] == fp
