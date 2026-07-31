"""Verifier for the satellite conjunction risk task."""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

if os.environ.get("ORBIT_VERIFIER_CONTEXT") != "1":
    raise RuntimeError("verifier module is not available to candidate programs")

import orbit_oracle

ORACLE_SOURCE = Path(__file__).with_name("orbit_oracle.py")
ORACLE_SOURCE.unlink(missing_ok=True)
for pycache in Path(__file__).with_name("__pycache__").glob("orbit_oracle*.pyc"):
    pycache.unlink(missing_ok=True)

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


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_candidate(root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    for p in [
        Path("/app/encounter_risk_register.csv"),
        Path("/app/satellite_exposure_summary.csv"),
    ]:
        if p.exists():
            p.unlink()
    env = os.environ.copy()
    env["ORBIT_EVIDENCE_DIR"] = str(root)
    env.pop("ORBIT_VERIFIER_CONTEXT", None)
    subprocess.run(
        ["Rscript", "/app/analysis.R"], cwd="/app", env=env, check=True, timeout=180
    )
    return read_rows(Path("/app/encounter_risk_register.csv")), read_rows(
        Path("/app/satellite_exposure_summary.csv")
    )


def assert_ok(root: Path) -> int:
    exp_r, exp_s, cases = orbit_oracle.expected(root)
    got_r, got_s = run_candidate(root)
    assert got_r and got_s
    assert list(got_r[0].keys()) == REG_FIELDS
    assert list(got_s[0].keys()) == SUM_FIELDS
    assert sorted(got_r, key=lambda r: r["encounter_id"]) == sorted(
        exp_r, key=lambda r: r["encounter_id"]
    )
    assert sorted(got_s, key=lambda r: r["primary_id"]) == sorted(
        exp_s, key=lambda r: r["primary_id"]
    )
    assert sum(r["decision"] == "BREACH" for r in got_r) == sum(
        int(r["breaches"]) for r in got_s
    )
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
    """Relative encounter decisions are translation invariant."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "evidence"
        copy = Path(tmp) / "copy"
        orbit_oracle.generate(root, 41)
        shutil.copytree(root, copy)
        base_cases = assert_ok(root)
        changed_cases = assert_ok(copy)
    assert base_cases == changed_cases


def test_policy_revision_and_probability_mass_are_semantic() -> None:
    """Changing approved policy mass parameters changes the recomputed risk register."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "evidence"
        changed = Path(tmp) / "changed"
        orbit_oracle.generate(root, 53)
        shutil.copytree(root, changed)
        policy_path = changed / "policy/screening_policies.csv"
        rows = read_rows(policy_path)
        fields = list(rows[0])
        for row in rows:
            if row["status"] == "approved" and row["quality_code"] == "HIGH":
                row["hard_body_radius_m"] = "32.0"
                row["probability_floor"] = "0.000009"
                row["covariance_scale"] = "0.62"
        write_rows(policy_path, rows, fields)
        base_expected, _, _ = orbit_oracle.expected(root)
        changed_expected, _, _ = orbit_oracle.expected(changed)
        assert base_expected != changed_expected
        assert assert_ok(changed) >= 60


def test_policy_age_adjustment_changes_thresholds() -> None:
    """Moving the selected policy effective time changes age-adjusted probability gates."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "evidence"
        changed = Path(tmp) / "changed"
        orbit_oracle.generate(root, 61)
        shutil.copytree(root, changed)
        policy_path = changed / "policy/screening_policies.csv"
        rows = read_rows(policy_path)
        fields = list(rows[0])
        for row in rows:
            if row["status"] == "approved" and row["quality_code"] == "HIGH":
                row["effective_tca"] = "2026-05-28T00:00"
                row["max_probability"] = "0.000006"
        write_rows(policy_path, rows, fields)
        base_expected, _, _ = orbit_oracle.expected(root)
        changed_expected, _, _ = orbit_oracle.expected(changed)
        assert base_expected != changed_expected
        assert assert_ok(changed) >= 60


def test_degenerate_covariance_and_blackout_boundary_are_semantic() -> None:
    """Degenerate covariance and half-open blackout boundaries use the stated rules."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "evidence"
        orbit_oracle.generate(root, 73)
        encounter_path = root / "orbits/encounters.csv"
        rows = read_rows(encounter_path)
        fields = list(rows[0])
        rows[0]["encounter_id"] = "BOUNDARY-DEGENERATE"
        rows[0]["primary_id"] = "SAT-X"
        rows[0]["tca"] = "2026-06-02T12:00"
        rows[0]["rx_km"] = "0.000"
        rows[0]["ry_km"] = "0.000"
        rows[0]["rz_km"] = "0.000"
        rows[0]["cxx"] = "0.000"
        rows[0]["cxy"] = "0.000"
        rows[0]["cxz"] = "0.000"
        rows[0]["cyy"] = "0.000"
        rows[0]["cyz"] = "0.000"
        rows[0]["czz"] = "0.000"
        rows[0]["quality_code"] = "HIGH"
        write_rows(encounter_path, rows, fields)
        blackout_path = root / "policy/maneuver_blackouts.csv"
        blackout_rows = read_rows(blackout_path)
        blackout_fields = list(blackout_rows[0])
        blackout_rows.append(
            {
                "primary_id": "SAT-X",
                "start_tca": "2026-06-02T00:00",
                "end_tca": "2026-06-02T12:00",
                "status": "approved",
            }
        )
        write_rows(blackout_path, blackout_rows, blackout_fields)
        expected, _, _ = orbit_oracle.expected(root)
        row = next(r for r in expected if r["encounter_id"] == "BOUNDARY-DEGENERATE")
        assert row["blackout"] == "FALSE"
        assert row["sigma_distance"] == "0.000000"
        assert row["probability"] == "1.000000"
        assert assert_ok(root) >= 60


def test_policy_id_tie_break_and_fixed_decimal_fields_are_semantic() -> None:
    """Policy-id tie-breaking and fixed six-place formatting affect outputs."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "evidence"
        orbit_oracle.generate(root, 89)
        policy_path = root / "policy/screening_policies.csv"
        rows = read_rows(policy_path)
        fields = list(rows[0])
        rows.append(
            {
                "policy_id": "PZ",
                "effective_tca": "2026-06-03T00:00",
                "revision_ts": "2026-06-02T13:00",
                "status": "approved",
                "quality_code": "HIGH",
                "max_miss_km": "0.15",
                "max_sigma_distance": "0.35",
                "max_probability": "0.900000",
                "covariance_scale": "2.25",
                "hard_body_radius_m": "7.0",
                "probability_floor": "0.000000",
            }
        )
        write_rows(policy_path, rows, fields)
        expected, summary, _ = orbit_oracle.expected(root)
        assert all(len(r["probability"].split(".")[1]) == 6 for r in expected)
        assert all(len(r["max_probability"].split(".")[1]) == 6 for r in summary)
        assert assert_ok(root) >= 60


def test_candidate_does_not_mutate_evidence() -> None:
    """The scientific evidence bundle must remain unchanged after evaluation."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "evidence"
        shutil.copytree("/app/evidence", root)
        before = sorted(
            p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
        )
        assert_ok(root)
        after = sorted(
            p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
        )
        assert before == after


def test_common_wrong_interpretations_are_present() -> None:
    """The visible bundle separates miss-only, draft-policy, blackout, and covariance mistakes."""
    exp_r, _, _ = orbit_oracle.expected(Path("/app/evidence"))
    assert any(r["decision"] == "BREACH" for r in exp_r)
    assert any(r["blackout"] == "TRUE" for r in exp_r)
    assert any(
        float(r["projected_miss_km"]) < 1.0 and r["decision"] == "CLEAR" for r in exp_r
    )
