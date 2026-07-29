"""Verifier for the satellite conjunction risk task."""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import orbit_oracle

REG_FIELDS = [
    "encounter_id",
    "primary_id",
    "secondary_id",
    "projected_miss_km",
    "sigma_distance",
    "probability",
    "blackout",
    "decision",
]
SUM_FIELDS = [
    "primary_id",
    "total_encounters",
    "breaches",
    "blackout_suppressed",
    "max_probability",
    "min_projected_miss_km",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def run_candidate(root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    for p in [Path("/app/encounter_risk_register.csv"), Path("/app/satellite_exposure_summary.csv")]:
        if p.exists():
            p.unlink()
    env = os.environ.copy()
    env["ORBIT_EVIDENCE_DIR"] = str(root)
    subprocess.run(["Rscript", "/app/analysis.R"], cwd="/app", env=env, check=True, timeout=180)
    return read_rows(Path("/app/encounter_risk_register.csv")), read_rows(Path("/app/satellite_exposure_summary.csv"))


def assert_ok(root: Path) -> int:
    exp_r, exp_s, cases = orbit_oracle.expected(root)
    got_r, got_s = run_candidate(root)
    assert got_r and got_s
    assert list(got_r[0].keys()) == REG_FIELDS
    assert list(got_s[0].keys()) == SUM_FIELDS
    assert sorted(got_r, key=lambda r: r["encounter_id"]) == sorted(exp_r, key=lambda r: r["encounter_id"])
    assert sorted(got_s, key=lambda r: r["primary_id"]) == sorted(exp_s, key=lambda r: r["primary_id"])
    assert sum(r["decision"] == "BREACH" for r in got_r) == sum(int(r["breaches"]) for r in got_s)
    return cases


def test_visible_evidence_matches_scientific_oracle() -> None:
    """Visible evidence checks covariance projection, blackout suppression, and policy revisions."""
    assert assert_ok(Path("/app/evidence")) >= 60


def test_private_variant_rejects_visible_hardcoding() -> None:
    """Fresh orbital evidence prevents copying visible decisions."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "evidence"
        orbit_oracle.generate(root, 17)
        assert assert_ok(root) >= 60


def test_private_variant_exercises_policy_and_geometry_edges() -> None:
    """A second variant stresses policy revisions, covariance shape, and blackout intervals."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "evidence"
        orbit_oracle.generate(root, 29)
        assert assert_ok(root) >= 60


def test_translation_metamorphism_preserves_risk() -> None:
    """Adding no absolute-origin field means relative encounter decisions are translation invariant."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "evidence"
        copy = Path(tmp) / "copy"
        orbit_oracle.generate(root, 41)
        shutil.copytree(root, copy)
        base_cases = assert_ok(root)
        changed_cases = assert_ok(copy)
    assert base_cases == changed_cases


def test_candidate_does_not_mutate_evidence() -> None:
    """The scientific evidence bundle must remain unchanged after evaluation."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "evidence"
        shutil.copytree("/app/evidence", root)
        before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
        assert_ok(root)
        after = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
        assert before == after


def test_common_wrong_interpretations_are_present() -> None:
    """The visible bundle separates miss-only, draft-policy, blackout, and covariance mistakes."""
    exp_r, _, _ = orbit_oracle.expected(Path("/app/evidence"))
    assert any(r["decision"] == "BREACH" for r in exp_r)
    assert any(r["blackout"] == "TRUE" for r in exp_r)
    assert any(float(r["projected_miss_km"]) < 1.0 and r["decision"] == "CLEAR" for r in exp_r)
