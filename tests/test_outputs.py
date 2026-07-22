"""Verifier for the native backend matrix workspace."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
OUT = APP / "output"
REPORT = OUT / "matrix_report.json"
MATRIX = APP / "contracts" / "matrix_arms.json"


def _load_matrix() -> dict:
    return json.loads(MATRIX.read_text())


def _run_matrix() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    if REPORT.exists():
        REPORT.unlink()
    proc = subprocess.run(
        ["bash", str(APP / "scripts" / "run_matrix.sh")],
        cwd=str(APP),
        capture_output=True,
        text=True,
        timeout=1200,
    )
    assert REPORT.is_file(), (
        f"matrix report missing after run_matrix (rc={proc.returncode}): "
        f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
    )
    return json.loads(REPORT.read_text())


@pytest.fixture(scope="module")
def report() -> dict:
    return _run_matrix()


def _arm(report: dict, arm_id: str) -> dict:
    for row in report.get("arms", []):
        if row.get("arm_id") == arm_id:
            return row
    raise AssertionError(f"arm {arm_id} missing from report")


def test_slot_parity_alpha(report: dict) -> None:
    """Release and LTO arms that share a backend must record the same digest."""
    b1 = _arm(report, "b1")
    d3 = _arm(report, "d3")
    assert b1["probe_ok"] == True  # noqa: E712
    assert d3["probe_ok"] == True  # noqa: E712
    assert isinstance(b1["digest"], int)
    assert b1["digest"] > 0
    assert b1["digest"] == d3["digest"]


def test_slot_parity_beta(report: dict) -> None:
    """Release and static arms that share a backend must record the same digest."""
    b1 = _arm(report, "b1")
    c2 = _arm(report, "c2")
    assert b1["probe_ok"] == True  # noqa: E712
    assert c2["probe_ok"] == True  # noqa: E712
    assert b1["digest"] == c2["digest"]
    assert c2["tag_p"] == c2["tag_q"]
    assert c2["tag_p"] == "t4"


def test_cross_lane_gamma(report: dict) -> None:
    """Static-link arm builds and its probe exits successfully with matching tags."""
    c2 = _arm(report, "c2")
    assert c2["build_ok"] == True  # noqa: E712
    assert c2["probe_ok"] == True  # noqa: E712
    assert c2["tag_agree"] == True  # noqa: E712
    assert c2["tag_p"] == c2["tag_q"]
    assert c2["tag_p"] == "t4"
    assert c2["mode"] == "static"


def test_cross_lane_delta(report: dict) -> None:
    """LTO multi-feature arm builds and its probe exits successfully."""
    d3 = _arm(report, "d3")
    assert d3["build_ok"] == True  # noqa: E712
    assert d3["probe_ok"] == True  # noqa: E712
    assert d3["mode"] == "lto"
    assert d3["tag_p"] == "t4"
    assert d3["tag_q"] == "t4"


def test_bait_split_epsilon(report: dict) -> None:
    """tag_agree must equal real tag equality; shared-backend digests must match."""
    for row in report.get("arms", []):
        tag_p = row["tag_p"]
        tag_q = row["tag_q"]
        agree = row["tag_agree"]
        assert agree == (tag_p == tag_q), (
            f"arm {row.get('arm_id')}: tag_agree={agree} but tags {tag_p!r} vs {tag_q!r}"
        )
    shared = report["shared_backend_digests"]["bx"]
    assert shared["identical"] == True  # noqa: E712
    digests = shared["digests"]
    assert len(digests) >= 2
    assert len(set(digests)) == 1
    assert digests[0] == digests[1]


def test_shape_zeta(report: dict) -> None:
    """Default/dev arm still builds and its probe exits successfully."""
    a0 = _arm(report, "a0")
    assert a0["build_ok"] == True  # noqa: E712
    assert a0["probe_ok"] == True  # noqa: E712
    assert a0["mode"] == "dev"
    assert a0["tag_p"] == "dev"
    assert a0["tag_q"] == "dev"


def test_emit_eta(report: dict) -> None:
    """Report comes from rebuilt /app artifacts; matrix still has all documented arms."""
    assert REPORT.is_file()
    assert report["schema_version"] == 1
    matrix = _load_matrix()
    arm_ids = [a["id"] for a in matrix["arms"]]
    assert len(arm_ids) >= 4
    for arm_id in arm_ids:
        found = list((APP / "target").glob(f"arm_{arm_id}/**/probe"))
        assert len(found) >= 1, f"missing rebuilt probe binary for arm {arm_id}"
        assert found[0].stat().st_size > 0


def test_digest_theta(report: dict) -> None:
    """Every documented arm is present, probes green, and features were not stripped."""
    matrix = _load_matrix()
    expected_ids = {a["id"] for a in matrix["arms"]}
    seen = {row["arm_id"] for row in report["arms"]}
    assert expected_ids == seen or expected_ids <= seen
    for row in report["arms"]:
        assert row["build_ok"] == True  # noqa: E712
        assert row["probe_ok"] == True  # noqa: E712
        assert isinstance(row["digest"], int)
        assert row["digest"] > 0
    shared = report["shared_backend_digests"]["bx"]
    assert shared["identical"] == True  # noqa: E712
    feats = {tuple(a.get("features") or []) for a in matrix["arms"]}
    assert ("bx",) in feats
    assert ("bx", "by") in feats
