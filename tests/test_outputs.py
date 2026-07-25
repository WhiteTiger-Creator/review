"""Behavioral checks for the powder TOF lattice refinement binary."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any

BIN = Path("/app/bin/ndref")
CFG = Path("/app/config/refine_policy.toml")
SEALED = Path("/app/data/sealed/production_policy.toml")
PEAKS = Path("/app/data/sample/peaks.csv")
INSTR = Path("/app/data/sample/instrument.json")
STRUCT = Path("/app/data/sample/reference_structure.json")

SAMPLE_SHA256 = {
    "peaks.csv": "eeb08162dc053b0c400d55135c0f7a7c519e3ed38ad84d4e786f00eb384a706d",
    "instrument.json": "95a97c5c5a71e5479924d481f45a010cd6a3360e9b08ebe0f88ee6fa8b128cb4",
    "reference_structure.json": "efa09368d33aeec7145fc980a99692f319fc4c3fa6edabeeb2cbd463722fe21c",
}
SEALED_SHA256 = "4a341fd52cfdb0cfd57dea613b5550732c97b9b64c132c18a8bad2b9734f3cb0"

SHIPPED: dict[str, Any] = {
    "schema_version": 2,
    "h_js": 6.62607015e-34,
    "m_n_kg": 1.67492749804e-27,
    "intensity_floor": 25.0,
    "residual_sigma_max": 4.0,
    "min_admitted_peaks": 4,
    "admit_mode": "intensity_and_extinction",
    "extinction_mode": "skip",
    "extinction_scale": 0.2,
    "policy_revision": "nd-desk-2026.07",
}

REPORT_KEYS = [
    "schema_version",
    "policy_revision",
    "crystal_system",
    "peak_count",
    "admitted_count",
    "rejected_count",
    "chi2",
    "rms_resid_A",
    "a_A",
    "b_A",
    "c_A",
    "alpha_deg",
    "beta_deg",
    "gamma_deg",
    "rejected_ids",
    "residuals",
    "refine_digest",
]

RESIDUAL_KEYS = [
    "peak_id",
    "h",
    "k",
    "l",
    "d_obs_A",
    "d_calc_A",
    "resid_sigma",
    "rejected",
]

STRUCT_KEYS = [
    "a_A",
    "b_A",
    "c_A",
    "alpha_deg",
    "beta_deg",
    "gamma_deg",
    "crystal_system",
]

PEAK_FIELDS = [
    "peak_id",
    "h",
    "k",
    "l",
    "tof_us",
    "intensity",
    "sigma_tof",
    "extinct_flag",
]


def fmt10(x: float) -> str:
    y = 0.0 if x == 0.0 else x
    text = f"{y:.10f}"
    return "0.0000000000" if text == "-0.0000000000" else text


def fmt8(x: float) -> str:
    y = 0.0 if x == 0.0 else x
    text = f"{y:.8f}"
    return "0.00000000" if text == "-0.00000000" else text


def _toml(pol: dict[str, Any]) -> str:
    lines: list[str] = []
    for k, v in pol.items():
        if isinstance(v, str):
            lines.append(f'{k} = "{v}"')
        else:
            lines.append(f"{k} = {v}")
    return "\n".join(lines) + "\n"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(BIN), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _rebuild() -> None:
    subprocess.run(["bash", "/app/build.sh"], check=True, capture_output=True, text=True)


def _restore_live_policy() -> None:
    CFG.write_text(SEALED.read_text(encoding="utf-8"), encoding="utf-8")


def _write_peaks(path: Path, peaks: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=PEAK_FIELDS)
        writer.writeheader()
        for peak in peaks:
            writer.writerow(peak)


def load_peaks(text: str) -> list[dict[str, Any]]:
    rows = list(csv.DictReader(text.splitlines()))
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "peak_id": row["peak_id"],
                "h": int(row["h"]),
                "k": int(row["k"]),
                "l": int(row["l"]),
                "tof_us": float(row["tof_us"]),
                "intensity": float(row["intensity"]),
                "sigma_tof": float(row["sigma_tof"]),
                "extinct_flag": int(row["extinct_flag"]),
            }
        )
    return out


def expect_pack(
    peaks: list[dict[str, Any]],
    instr: dict[str, float],
    crystal_system: str,
    pol: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    h_js = float(pol["h_js"])
    m_n = float(pol["m_n_kg"])
    path_m = float(instr["L1_m"]) + float(instr["L2_m"])
    sin_theta = math.sin(math.radians(float(instr["two_theta_deg"]) / 2.0))
    offset = float(instr["pulse_offset_us"])

    states: list[dict[str, Any]] = []
    for peak in peaks:
        t_s = (peak["tof_us"] - offset) * 1e-6
        sigma_t = peak["sigma_tof"] * 1e-6
        d_m = h_js * t_s / (2.0 * path_m * sin_theta * m_n)
        sd_m = h_js * sigma_t / (2.0 * path_m * sin_theta * m_n)
        d_obs = d_m * 1e10
        sigma_d = sd_m * 1e10
        primary = peak["intensity"] < float(pol["intensity_floor"])
        if (
            pol["admit_mode"] == "intensity_and_extinction"
            and peak["extinct_flag"] == 1
            and pol["extinction_mode"] == "skip"
        ):
            primary = True
        sigma_q = 2.0 * sigma_d / (d_obs**3)
        weight = 1.0 / (sigma_q * sigma_q)
        if peak["extinct_flag"] == 1 and pol["extinction_mode"] == "downweight":
            weight *= float(pol["extinction_scale"])
        states.append(
            {
                **peak,
                "d_obs_A": d_obs,
                "sigma_d_A": sigma_d,
                "weight": 0.0 if primary else weight,
                "primary_reject": primary,
                "rejected": primary,
                "residual_reject": False,
                "d_calc_A": 0.0,
                "resid_sigma": 0.0,
            }
        )

    def design_row(h: int, k: int, ell: int) -> list[float]:
        if crystal_system == "cubic":
            return [float(h * h + k * k + ell * ell)]
        if crystal_system == "tetragonal":
            return [float(h * h + k * k), float(ell * ell)]
        if crystal_system == "orthorhombic":
            return [float(h * h), float(k * k), float(ell * ell)]
        if crystal_system == "hexagonal":
            return [(4.0 / 3.0) * (h * h + h * k + k * k), float(ell * ell)]
        raise AssertionError("unsupported")

    def fit(active: list[dict[str, Any]]) -> dict[str, float]:
        assert len(active) >= int(pol["min_admitted_peaks"])
        ncols = len(design_row(active[0]["h"], active[0]["k"], active[0]["l"]))
        ata = [[0.0] * ncols for _ in range(ncols)]
        atq = [0.0] * ncols
        for st in active:
            row = design_row(st["h"], st["k"], st["l"])
            q_obs = 1.0 / (st["d_obs_A"] ** 2)
            weight = st["weight"]
            for col in range(ncols):
                atq[col] += weight * row[col] * q_obs
                for row_i in range(ncols):
                    ata[row_i][col] += weight * row[row_i] * row[col]
        aug = [ata[r][:] + [atq[r]] for r in range(ncols)]
        for col in range(ncols):
            pivot = max(range(col, ncols), key=lambda r: abs(aug[r][col]))
            assert abs(aug[pivot][col]) > 0
            aug[col], aug[pivot] = aug[pivot], aug[col]
            piv = aug[col][col]
            for c in range(col, ncols + 1):
                aug[col][c] /= piv
            for r in range(ncols):
                if r == col:
                    continue
                factor = aug[r][col]
                for c in range(col, ncols + 1):
                    aug[r][c] -= factor * aug[col][c]
        x = [aug[r][ncols] for r in range(ncols)]
        if crystal_system == "cubic":
            a = 1.0 / math.sqrt(x[0])
            return {
                "a_A": a,
                "b_A": a,
                "c_A": a,
                "alpha_deg": 90.0,
                "beta_deg": 90.0,
                "gamma_deg": 90.0,
            }
        if crystal_system == "tetragonal":
            a = 1.0 / math.sqrt(x[0])
            c = 1.0 / math.sqrt(x[1])
            return {
                "a_A": a,
                "b_A": a,
                "c_A": c,
                "alpha_deg": 90.0,
                "beta_deg": 90.0,
                "gamma_deg": 90.0,
            }
        if crystal_system == "orthorhombic":
            return {
                "a_A": 1.0 / math.sqrt(x[0]),
                "b_A": 1.0 / math.sqrt(x[1]),
                "c_A": 1.0 / math.sqrt(x[2]),
                "alpha_deg": 90.0,
                "beta_deg": 90.0,
                "gamma_deg": 90.0,
            }
        a = 1.0 / math.sqrt(x[0])
        c = 1.0 / math.sqrt(x[1])
        return {
            "a_A": a,
            "b_A": a,
            "c_A": c,
            "alpha_deg": 90.0,
            "beta_deg": 90.0,
            "gamma_deg": 120.0,
        }

    def d_calc(cell: dict[str, float], h: int, k: int, ell: int) -> float:
        if crystal_system == "hexagonal":
            q = (4.0 / 3.0) * (h * h + h * k + k * k) / (cell["a_A"] ** 2) + (ell * ell) / (
                cell["c_A"] ** 2
            )
        else:
            q = (h / cell["a_A"]) ** 2 + (k / cell["b_A"]) ** 2 + (ell / cell["c_A"]) ** 2
        return 1.0 / math.sqrt(q)

    def apply_residuals(cell: dict[str, float]) -> None:
        for st in states:
            st["d_calc_A"] = d_calc(cell, st["h"], st["k"], st["l"])
            st["resid_sigma"] = (st["d_obs_A"] - st["d_calc_A"]) / st["sigma_d_A"]

    def refresh_residual_flags() -> None:
        for st in states:
            st["residual_reject"] = (not st["primary_reject"]) and abs(st["resid_sigma"]) > float(
                pol["residual_sigma_max"]
            )
            st["rejected"] = st["primary_reject"] or st["residual_reject"]

    cell = fit([st for st in states if not st["rejected"]])
    apply_residuals(cell)
    any_resid = False
    for st in states:
        if (not st["primary_reject"]) and abs(st["resid_sigma"]) > float(pol["residual_sigma_max"]):
            st["residual_reject"] = True
            st["rejected"] = True
            any_resid = True
    if any_resid:
        cell = fit([st for st in states if not st["rejected"]])
        apply_residuals(cell)
        refresh_residual_flags()

    admitted = [st for st in states if not st["rejected"]]
    assert admitted
    chi2 = sum(st["resid_sigma"] ** 2 for st in admitted)
    rms = math.sqrt(
        sum((st["d_obs_A"] - st["d_calc_A"]) ** 2 for st in admitted) / len(admitted)
    )
    states.sort(key=lambda st: st["peak_id"])
    rejected_ids = [st["peak_id"] for st in states if st["rejected"]]

    lines = [f"rev:{pol['policy_revision']}"]
    for st in states:
        rej = "1" if st["rejected"] else "0"
        lines.append(
            f"{st['peak_id']}:{fmt10(st['d_obs_A'])}:{fmt10(st['d_calc_A'])}:{fmt10(st['resid_sigma'])}:{rej}"
        )
    lines.append(
        f"a:{fmt10(cell['a_A'])}:b:{fmt10(cell['b_A'])}:c:{fmt10(cell['c_A'])}:chi2:{fmt10(chi2)}:rms:{fmt10(rms)}"
    )
    digest = hashlib.sha256("\n".join(lines).encode()).hexdigest()

    report = {
        "schema_version": int(pol["schema_version"]),
        "policy_revision": pol["policy_revision"],
        "crystal_system": crystal_system,
        "peak_count": len(states),
        "admitted_count": len(admitted),
        "rejected_count": len(rejected_ids),
        "chi2": chi2,
        "rms_resid_A": rms,
        "a_A": cell["a_A"],
        "b_A": cell["b_A"],
        "c_A": cell["c_A"],
        "alpha_deg": cell["alpha_deg"],
        "beta_deg": cell["beta_deg"],
        "gamma_deg": cell["gamma_deg"],
        "rejected_ids": rejected_ids,
        "refine_digest": digest,
        "residuals": [
            {
                "peak_id": st["peak_id"],
                "h": st["h"],
                "k": st["k"],
                "l": st["l"],
                "d_obs_A": st["d_obs_A"],
                "d_calc_A": st["d_calc_A"],
                "resid_sigma": st["resid_sigma"],
                "rejected": st["rejected"],
            }
            for st in states
        ],
    }
    refined = {
        "a_A": cell["a_A"],
        "b_A": cell["b_A"],
        "c_A": cell["c_A"],
        "alpha_deg": cell["alpha_deg"],
        "beta_deg": cell["beta_deg"],
        "gamma_deg": cell["gamma_deg"],
        "crystal_system": crystal_system,
    }
    return refined, report


def _top_keys(raw: str) -> list[str]:
    return re.findall(r'\n  "([^"]+)":', raw)


def test_beamline_fixtures_remain_byte_stable():
    """Shipped sample peaks/instrument/structure and sealed policy must keep verifier hashes."""
    assert _sha(PEAKS) == SAMPLE_SHA256["peaks.csv"]
    assert _sha(INSTR) == SAMPLE_SHA256["instrument.json"]
    assert _sha(STRUCT) == SAMPLE_SHA256["reference_structure.json"]
    assert _sha(SEALED) == SEALED_SHA256


def test_orthorhombic_desk_pack_writes_cell_and_reject_digest():
    """Default orthorhombic pack exits 1, rejects P09 only, and matches cell/digest contracts."""
    _restore_live_policy()
    _rebuild()
    refined_path = Path("/tmp/ndref-default-refined.json")
    report_path = Path("/tmp/ndref-default-report.json")
    for path in (refined_path, report_path):
        if path.exists():
            path.unlink()
    proc = _run(["--refined", str(refined_path), "--report", str(report_path)])
    assert proc.returncode == 1, proc.stderr
    assert proc.stdout == ""
    peaks = load_peaks(PEAKS.read_text(encoding="utf-8"))
    instr = json.loads(INSTR.read_text(encoding="utf-8"))
    exp_ref, exp_rep = expect_pack(peaks, instr, "orthorhombic", SHIPPED)
    got_ref = json.loads(refined_path.read_text(encoding="utf-8"))
    got_rep = json.loads(report_path.read_text(encoding="utf-8"))
    for key in ("a_A", "b_A", "c_A"):
        assert abs(got_ref[key] - exp_ref[key]) < 1e-8
        assert abs(float(got_rep[key]) - exp_ref[key]) < 1e-8
    assert got_rep["rejected_ids"] == ["P09"]
    assert got_rep["rejected_count"] == 1
    assert got_rep["refine_digest"] == exp_rep["refine_digest"]
    assert abs(got_rep["chi2"] - exp_rep["chi2"]) < 1e-8
    raw_rep = report_path.read_text(encoding="utf-8")
    assert _top_keys(raw_rep) == REPORT_KEYS
    assert raw_rep.endswith("}\n")
    raw_ref = refined_path.read_text(encoding="utf-8")
    assert _top_keys(raw_ref) == STRUCT_KEYS
    assert raw_ref.endswith("}\n")
    assert list(got_rep["residuals"][0].keys()) == RESIDUAL_KEYS


def test_default_config_path_requires_sealed_byte_match():
    """Drifted live `/app/config/refine_policy.toml` is fatal and must not clobber outputs."""
    _rebuild()
    CFG.write_text(_toml({**SHIPPED, "policy_revision": "drifted"}), encoding="utf-8")
    out_r = Path("/tmp/ndref-drift-refined.json")
    out_p = Path("/tmp/ndref-drift-report.json")
    marker = '{"keep":true}\n'
    out_r.write_text(marker, encoding="utf-8")
    out_p.write_text(marker, encoding="utf-8")
    proc = _run(["--refined", str(out_r), "--report", str(out_p)])
    assert proc.returncode == 2
    assert out_r.read_text(encoding="utf-8") == marker
    assert out_p.read_text(encoding="utf-8") == marker
    _restore_live_policy()


def test_unknown_flag_exits_fatal_without_touching_artifacts():
    """Unknown flags exit 2 with stderr diagnostics and leave preexisting artifacts intact."""
    _restore_live_policy()
    _rebuild()
    out_r = Path("/tmp/ndref-badflag-refined.json")
    out_p = Path("/tmp/ndref-badflag-report.json")
    marker = '{"keep":true}\n'
    out_r.write_text(marker, encoding="utf-8")
    out_p.write_text(marker, encoding="utf-8")
    proc = _run(["--not-a-flag", "x", "--refined", str(out_r), "--report", str(out_p)])
    assert proc.returncode == 2
    assert proc.stderr.strip() != ""
    assert out_r.read_text(encoding="utf-8") == marker
    assert out_p.read_text(encoding="utf-8") == marker


def test_duplicate_peak_id_is_fatal_before_emit():
    """Duplicate peak_id values exit 2 and must not create refined/report paths."""
    _restore_live_policy()
    _rebuild()
    lines = PEAKS.read_text(encoding="utf-8").splitlines()
    cols = lines[2].split(",")
    cols[0] = lines[1].split(",")[0]
    lines[2] = ",".join(cols)
    bad = Path("/tmp/ndref-dup-peaks.csv")
    bad.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out_r = Path("/tmp/ndref-dup-refined.json")
    out_p = Path("/tmp/ndref-dup-report.json")
    if out_r.exists():
        out_r.unlink()
    if out_p.exists():
        out_p.unlink()
    proc = _run(
        [
            "--peaks",
            str(bad),
            "--config",
            str(SEALED),
            "--refined",
            str(out_r),
            "--report",
            str(out_p),
        ]
    )
    assert proc.returncode == 2
    assert not out_r.exists()
    assert not out_p.exists()


def test_intensity_floor_admit_keeps_bright_extinct_peak():
    """Under intensity_floor admit_mode, an extinct peak above the floor stays admitted."""
    _restore_live_policy()
    _rebuild()
    pol = {
        **SHIPPED,
        "admit_mode": "intensity_floor",
        "extinction_mode": "skip",
        "intensity_floor": 10.0,
        "policy_revision": "floor-only",
    }
    cfg = Path("/tmp/ndref-floor.toml")
    cfg.write_text(_toml(pol), encoding="utf-8")
    peaks = load_peaks(PEAKS.read_text(encoding="utf-8"))
    for peak in peaks:
        if peak["peak_id"] == "P09":
            peak["intensity"] = 40.0
            peak["extinct_flag"] = 1
    peak_path = Path("/tmp/ndref-floor-peaks.csv")
    _write_peaks(peak_path, peaks)
    instr = json.loads(INSTR.read_text(encoding="utf-8"))
    exp_ref, exp_rep = expect_pack(peaks, instr, "orthorhombic", pol)
    out_r = Path("/tmp/ndref-floor-refined.json")
    out_p = Path("/tmp/ndref-floor-report.json")
    proc = _run(
        [
            "--peaks",
            str(peak_path),
            "--config",
            str(cfg),
            "--refined",
            str(out_r),
            "--report",
            str(out_p),
        ]
    )
    assert proc.returncode == (0 if exp_rep["rejected_count"] == 0 else 1)
    got = json.loads(out_p.read_text(encoding="utf-8"))
    assert "P09" not in got["rejected_ids"]
    assert got["refine_digest"] == exp_rep["refine_digest"]
    assert abs(json.loads(out_r.read_text(encoding="utf-8"))["a_A"] - exp_ref["a_A"]) < 1e-8


def test_tof_outlier_refit_clears_collateral_residual_flags():
    """After the single residual re-fit, reject flags must be refreshed against the final cell.

    A +80 us TOF bump on P07 can make collateral peaks look bad on the first fit; once P07
    is excluded and the cell is re-solved, those collateral peaks must clear if they now
    pass residual_sigma_max. Sticky first-pass residual rejects are incorrect.
    """
    _restore_live_policy()
    _rebuild()
    peaks = load_peaks(PEAKS.read_text(encoding="utf-8"))
    for peak in peaks:
        if peak["peak_id"] == "P07":
            peak["tof_us"] += 80.0
    peak_path = Path("/tmp/ndref-outlier-peaks.csv")
    _write_peaks(peak_path, peaks)
    instr = json.loads(INSTR.read_text(encoding="utf-8"))
    _, exp_rep = expect_pack(peaks, instr, "orthorhombic", SHIPPED)
    assert exp_rep["rejected_ids"] == ["P07", "P09"]
    assert "P01" not in exp_rep["rejected_ids"]
    out_r = Path("/tmp/ndref-outlier-refined.json")
    out_p = Path("/tmp/ndref-outlier-report.json")
    proc = _run(
        [
            "--peaks",
            str(peak_path),
            "--config",
            str(SEALED),
            "--refined",
            str(out_r),
            "--report",
            str(out_p),
        ]
    )
    assert proc.returncode == 1
    got = json.loads(out_p.read_text(encoding="utf-8"))
    assert got["rejected_ids"] == ["P07", "P09"]
    assert "P01" not in got["rejected_ids"]
    by_id = {row["peak_id"]: row for row in got["residuals"]}
    assert by_id["P01"]["rejected"] is False
    assert by_id["P07"]["rejected"] is True
    assert by_id["P09"]["rejected"] is True
    assert got["refine_digest"] == exp_rep["refine_digest"]


def test_hexagonal_metric_recovers_locked_angles():
    """Hexagonal 4/3 Q-rows recover a/c with locked angles; digest uses canonical zero text."""
    _restore_live_policy()
    _rebuild()
    a_true, c_true = 3.2, 5.1
    h_js = SHIPPED["h_js"]
    m_n = SHIPPED["m_n_kg"]
    instr = {"L1_m": 10.0, "L2_m": 2.0, "two_theta_deg": 90.0, "pulse_offset_us": 10.0}
    path_m = instr["L1_m"] + instr["L2_m"]
    sin_theta = math.sin(math.radians(instr["two_theta_deg"] / 2.0))
    miller = [(1, 0, 0), (1, 0, 1), (1, 1, 0), (0, 0, 2), (2, 0, 1), (1, 1, 2)]
    peaks: list[dict[str, Any]] = []
    for idx, (h, k, ell) in enumerate(miller, 1):
        q = (4.0 / 3.0) * (h * h + h * k + k * k) / (a_true * a_true) + (ell * ell) / (
            c_true * c_true
        )
        d_a = 1.0 / math.sqrt(q)
        t_s = (d_a * 1e-10) * 2.0 * path_m * sin_theta * m_n / h_js
        peaks.append(
            {
                "peak_id": f"H{idx:02d}",
                "h": h,
                "k": k,
                "l": ell,
                "tof_us": t_s * 1e6 + instr["pulse_offset_us"],
                "intensity": 200.0,
                "sigma_tof": 2.0,
                "extinct_flag": 0,
            }
        )
    peak_path = Path("/tmp/ndref-hex-peaks.csv")
    _write_peaks(peak_path, peaks)
    instr_path = Path("/tmp/ndref-hex-instrument.json")
    instr_path.write_text(json.dumps(instr, indent=2) + "\n", encoding="utf-8")
    struct_path = Path("/tmp/ndref-hex-structure.json")
    struct_path.write_text(
        json.dumps(
            {
                "a_A": 3.25,
                "b_A": 3.25,
                "c_A": 5.20,
                "alpha_deg": 90.0,
                "beta_deg": 90.0,
                "gamma_deg": 120.0,
                "crystal_system": "hexagonal",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _, exp_rep = expect_pack(peaks, instr, "hexagonal", SHIPPED)
    out_r = Path("/tmp/ndref-hex-refined.json")
    out_p = Path("/tmp/ndref-hex-report.json")
    proc = _run(
        [
            "--peaks",
            str(peak_path),
            "--instrument",
            str(instr_path),
            "--structure",
            str(struct_path),
            "--config",
            str(SEALED),
            "--refined",
            str(out_r),
            "--report",
            str(out_p),
        ]
    )
    assert proc.returncode == 0, proc.stderr
    raw_rep = out_p.read_text(encoding="utf-8")
    got_ref = json.loads(out_r.read_text(encoding="utf-8"))
    got_rep = json.loads(raw_rep)
    assert abs(got_ref["a_A"] - a_true) < 1e-6
    assert abs(got_ref["c_A"] - c_true) < 1e-6
    assert got_ref["gamma_deg"] == 120.0
    assert got_rep["refine_digest"] == exp_rep["refine_digest"]
    assert got_rep["rejected_count"] == 0
    assert "-0.0000000000" not in raw_rep


def test_orthorhombic_angle_lock_violation_is_fatal():
    """Reference orthorhombic cells with unlocked beta exit 2 without writing artifacts."""
    _restore_live_policy()
    _rebuild()
    bad = Path("/tmp/ndref-bad-angles.json")
    bad.write_text(
        json.dumps(
            {
                "a_A": 5.0,
                "b_A": 5.1,
                "c_A": 5.2,
                "alpha_deg": 90.0,
                "beta_deg": 91.0,
                "gamma_deg": 90.0,
                "crystal_system": "orthorhombic",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    out_r = Path("/tmp/ndref-badang-refined.json")
    out_p = Path("/tmp/ndref-badang-report.json")
    if out_r.exists():
        out_r.unlink()
    if out_p.exists():
        out_p.unlink()
    proc = _run(
        [
            "--structure",
            str(bad),
            "--config",
            str(SEALED),
            "--refined",
            str(out_r),
            "--report",
            str(out_p),
        ]
    )
    assert proc.returncode == 2
    assert not out_r.exists()
    assert not out_p.exists()


def test_flag_permutation_matches_canonical_digest():
    """Flag order must not change exit status or refine_digest on the sample pack."""
    _restore_live_policy()
    _rebuild()
    out_r = Path("/tmp/ndref-order-refined.json")
    out_p = Path("/tmp/ndref-order-report.json")
    proc = _run(
        [
            "--report",
            str(out_p),
            "--config",
            str(SEALED),
            "--refined",
            str(out_r),
            "--structure",
            str(STRUCT),
            "--instrument",
            str(INSTR),
            "--peaks",
            str(PEAKS),
        ]
    )
    assert proc.returncode == 1
    assert proc.stdout == ""
    peaks = load_peaks(PEAKS.read_text(encoding="utf-8"))
    instr = json.loads(INSTR.read_text(encoding="utf-8"))
    _, exp_rep = expect_pack(peaks, instr, "orthorhombic", SHIPPED)
    got = json.loads(out_p.read_text(encoding="utf-8"))
    assert got["refine_digest"] == exp_rep["refine_digest"]


def test_admitted_and_reject_paths_keep_stdout_empty():
    """Exit 0/1 paths must leave stdout empty while still writing both artifacts."""
    _restore_live_policy()
    _rebuild()
    out_r = Path("/tmp/ndref-stdout-refined.json")
    out_p = Path("/tmp/ndref-stdout-report.json")
    proc = _run(["--config", str(SEALED), "--refined", str(out_r), "--report", str(out_p)])
    assert proc.returncode in (0, 1)
    assert proc.stdout == ""
    assert out_r.exists() and out_p.exists()


def test_digest_tracks_refined_cell_not_reference_guess():
    """refine_digest must reflect the fitted cell, not the scratched reference lengths."""
    _restore_live_policy()
    _rebuild()
    out_r = Path("/tmp/ndref-mut-refined.json")
    out_p = Path("/tmp/ndref-mut-report.json")
    proc = _run(["--config", str(SEALED), "--refined", str(out_r), "--report", str(out_p)])
    assert proc.returncode == 1
    peaks = load_peaks(PEAKS.read_text(encoding="utf-8"))
    instr = json.loads(INSTR.read_text(encoding="utf-8"))
    _, exp_rep = expect_pack(peaks, instr, "orthorhombic", SHIPPED)
    got = json.loads(out_p.read_text(encoding="utf-8"))
    assert got["refine_digest"] == exp_rep["refine_digest"]
    assert got["a_A"] != 5.15
