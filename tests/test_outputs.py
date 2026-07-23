"""tests for the periodic plume inversion and flyby portfolio program."""

from __future__ import annotations

import csv
import itertools
import math
import shutil
import sqlite3
import subprocess
from pathlib import Path

import numpy as np
import pytest


JANET = "/usr/local/bin/janet"
MAIN = "/app/src/main.janet"
BASE_ROOT = Path("/tmp/plume_verifier_input")
BASE_OUTPUT = Path("/app/output")
BASE_DB = BASE_OUTPUT / "plume.db"
CANDIDATE_CWD = "/app"
CANDIDATE_PREFIX = [
    "/usr/bin/setpriv",
    "--reuid=65534",
    "--regid=65534",
    "--clear-groups",
    "--no-new-privs",
]

CONTROL_HEADER = (
    "phases,eccentricity,ocean_pressure,temperature,cubic,memory,ridge,tv,"
    "tv_eps,edge_threshold,source_total,design_noise,signal_rho,portfolio_size,"
    "portfolio_dose,phase_gap"
)
CONTROL_ROW = (
    "24,0.0047,7.6,268.4,0.018,0.32,0.04,0.08,0.02,0.46,1.0,0.035,"
    "0.25,3,0.20,4"
)
FRACTURE_HEADER = (
    "id,shell_km,depth_km,viscosity,base_mm,coupling,phase_offset,"
    "salinity_ppt,gas_ppm"
)
FRACTURE_ROWS = [
    "baghdad,24.0,6.2,1.15,0.42,0.18,0.0,18.0,900.0",
    "cairo,31.0,5.5,1.80,0.28,0.12,0.65,35.0,1500.0",
    "damascus,19.0,6.8,0.85,0.58,0.20,1.30,12.0,600.0",
    "alexandria,27.0,4.9,1.35,0.36,0.16,2.05,42.0,2200.0",
    "camphor,22.0,6.0,1.05,0.50,0.14,2.70,25.0,1100.0",
]
CANDIDATE_HEADER = "candidate,phase,altitude_km,speed_kms,dose_limit"
CANDIDATE_ROWS = [
    "orbiter-a,2,42,7.5,0.060",
    "orbiter-b,6,65,6.2,0.030",
    "orbiter-c,10,90,5.5,0.050",
    "orbiter-d,14,35,8.1,0.080",
    "orbiter-e,18,120,4.8,0.100",
    "orbiter-f,22,55,6.8,0.090",
]
OBS_HEADER = "phase,m18,m44,brightness,sigma_m18,sigma_m44,sigma_brightness"
OBS_ROWS = [
    "0,0.00350515231936326,0.004927833775649793,0.06766572402233269,0.025,0.018,0.03",
    "1,0.008746300361401272,0.0034028012290895464,0.060809576038850115,0.025,0.018,0.03",
    "2,0.0007781312666701914,0.0005896515492778869,0.05709817419551737,0.025,0.018,0.03",
    "3,-0.003530175493383213,-0.001598624495730434,0.049254292865274794,0.025,0.018,0.03",
    "4,0.0048784766142330694,-0.0016376871699316595,0.04152283506856471,0.025,0.018,0.03",
    "5,0.006759151525680967,0.0004501384691746751,0.03443079848539287,0.025,0.018,0.03",
    "7,-0.00159128553492676,0.0033384580526768758,0.030888554014433085,0.025,0.018,0.03",
    "8,-0.0004704865970671804,0.004780660751145506,0.03254523652243421,0.025,0.018,0.03",
    "9,0.009784850333215757,0.004371487637838994,0.03920274759926891,0.025,0.018,0.03",
    "10,0.0082124217621332,0.0024769556166348624,0.048769116175654596,0.025,0.018,0.03",
    "11,0.0010829651336885255,0.0010348517610771954,0.060053189400222765,0.025,0.018,0.03",
    "12,0.007432551864832641,0.0019120268529687254,0.07377373599399337,0.025,0.018,0.03",
    "13,0.015791122615551892,0.004802811148716729,0.08716989958137725,0.025,0.018,0.03",
    "14,0.01042955193976638,0.008037543347732592,0.09858038744962751,0.025,0.018,0.03",
    "15,0.006193263871461803,0.009611533756761756,0.10679234126006883,0.025,0.018,0.03",
    "16,0.014639563271892732,0.008651629221197521,0.111267814999576,0.025,0.018,0.03",
    "18,0.016744349689399994,0.005528339157081339,0.10782283883195243,0.025,0.018,0.03",
    "19,0.006962234143090221,0.0030080396593719244,0.10319287334442168,0.025,0.018,0.03",
    "20,0.004818964506686612,0.0024099035414351993,0.09691875111532593,0.025,0.018,0.03",
    "21,0.01241116885873505,0.0037407336233664023,0.08993058340562235,0.025,0.018,0.03",
    "23,0.008505192451936237,0.004912833109101092,0.07564355031299201,0.025,0.018,0.03",
]

EXPECTED_SCHEMA = {
    "state": [
        (0, "phase", "INTEGER", 1, None, 1),
        (1, "fracture", "TEXT", 1, None, 2),
        (2, "opening_mm", "REAL", 1, None, 0),
        (3, "water_flux", "REAL", 1, None, 0),
        (4, "m18", "REAL", 1, None, 0),
        (5, "m44", "REAL", 1, None, 0),
        (6, "brightness", "REAL", 1, None, 0),
    ],
    "reconstruction": [
        (0, "fracture", "TEXT", 0, None, 1),
        (1, "weight", "REAL", 1, None, 0),
    ],
    "flyby": [
        (0, "candidate", "TEXT", 0, None, 1),
        (1, "score", "REAL", 1, None, 0),
        (2, "dose", "REAL", 1, None, 0),
        (3, "feasible", "INTEGER", 1, None, 0),
        (4, "selected", "INTEGER", 1, None, 0),
    ],
    "portfolio": [
        (0, "score", "REAL", 1, None, 0),
        (1, "total_dose", "REAL", 1, None, 0),
    ],
}


def _records(header: str, rows: list[str]) -> list[dict[str, str]]:
    return list(csv.DictReader([header, *rows]))


def _write_case(
    root: Path,
    control_row: str = CONTROL_ROW,
    fracture_rows: list[str] | None = None,
    observation_rows: list[str] | None = None,
    candidate_rows: list[str] | None = None,
) -> None:
    shutil.rmtree(root, ignore_errors=True)
    observations = root / "observations"
    observations.mkdir(parents=True)
    (root / "control.csv").write_text(
        f"{CONTROL_HEADER}\n{control_row}\n", encoding="utf-8"
    )
    fractures = FRACTURE_ROWS if fracture_rows is None else fracture_rows
    (root / "fractures.csv").write_text(
        f"{FRACTURE_HEADER}\n" + "\n".join(fractures) + "\n", encoding="utf-8"
    )
    candidates = CANDIDATE_ROWS if candidate_rows is None else candidate_rows
    (root / "candidates.csv").write_text(
        f"{CANDIDATE_HEADER}\n" + "\n".join(candidates) + "\n",
        encoding="utf-8",
    )
    rows = OBS_ROWS if observation_rows is None else observation_rows
    for index, row in enumerate(rows):
        (observations / f"obs_{index:02d}.csv").write_text(
            f"{OBS_HEADER}\n{row}\n", encoding="utf-8"
        )


def _run(root: Path, output: Path) -> subprocess.CompletedProcess[str]:
    if output.exists():
        output.chmod(0o777)
    else:
        parent_existed = output.parent.exists()
        output.parent.mkdir(parents=True, exist_ok=True)
        if not parent_existed:
            output.parent.chmod(0o777)
    return subprocess.run(
        [*CANDIDATE_PREFIX, JANET, MAIN, str(root), str(output)],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=CANDIDATE_CWD,
        env={
            "HOME": "/tmp",
            "LANG": "C.UTF-8",
            "PATH": "/usr/local/bin:/usr/bin:/bin",
        },
    )


def _float_row(row: dict[str, str], text: set[str]) -> dict[str, float | str]:
    return {key: value if key in text else float(value) for key, value in row.items()}


def _inputs(
    control_row: str = CONTROL_ROW,
    fracture_rows: list[str] | None = None,
    observation_rows: list[str] | None = None,
    candidate_rows: list[str] | None = None,
) -> tuple[
    dict[str, float],
    list[dict[str, float | str]],
    list[dict[str, float]],
    list[dict[str, float | str]],
]:
    control = _float_row(_records(CONTROL_HEADER, [control_row])[0], set())
    fractures = [
        _float_row(row, {"id"})
        for row in _records(
            FRACTURE_HEADER,
            FRACTURE_ROWS if fracture_rows is None else fracture_rows,
        )
    ]
    observations = [
        _float_row(row, set())
        for row in _records(
            OBS_HEADER, OBS_ROWS if observation_rows is None else observation_rows
        )
    ]
    candidates = [
        _float_row(row, {"candidate"})
        for row in _records(
            CANDIDATE_HEADER,
            CANDIDATE_ROWS if candidate_rows is None else candidate_rows,
        )
    ]
    return control, fractures, observations, candidates


def _solve_states(
    control: dict[str, float], fractures: list[dict[str, float | str]]
) -> tuple[list[list[dict[str, float | str]]], np.ndarray, np.ndarray]:
    phases = int(control["phases"])
    count = len(fractures)
    drives = np.zeros((phases, count))
    edges = np.zeros((phases, count))
    for phase in range(phases):
        theta = 2.0 * math.pi * phase / phases
        for index, fracture in enumerate(fractures):
            drives[phase, index] = (
                fracture["base_mm"]
                + 900.0
                * control["eccentricity"]
                * math.cos(theta + fracture["phase_offset"])
                / fracture["shell_km"]
                + 0.025 * (control["ocean_pressure"] - fracture["depth_km"])
                + 0.00005 * fracture["gas_ppm"]
                + 0.003
                * (
                    control["temperature"]
                    - 273.15
                    + 0.055 * fracture["salinity_ppt"]
                )
            )
        for index, fracture in enumerate(fractures):
            if (
                drives[phase, index] > control["edge_threshold"]
                and drives[phase, (index + 1) % count] > control["edge_threshold"]
            ):
                edges[phase, index] = fracture["coupling"]

    opening = np.maximum(drives, 0.0)
    for _ in range(30):
        residual = np.zeros(phases * count)
        jacobian = np.zeros((phases * count, phases * count))
        for phase in range(phases):
            before = (phase - 1) % phases
            after = (phase + 1) % phases
            for index, fracture in enumerate(fractures):
                previous = (index - 1) % count
                following = (index + 1) % count
                left = edges[phase, previous]
                right = edges[phase, index]
                row = phase * count + index
                value = opening[phase, index]
                residual[row] = (
                    value
                    + control["cubic"] * fracture["viscosity"] * value**3
                    + control["memory"]
                    * (
                        2.0 * value
                        - opening[before, index]
                        - opening[after, index]
                    )
                    + left * (value - opening[phase, previous])
                    + right * (value - opening[phase, following])
                    - max(0.0, drives[phase, index])
                )
                jacobian[row, row] = (
                    1.0
                    + 3.0
                    * control["cubic"]
                    * fracture["viscosity"]
                    * value**2
                    + 2.0 * control["memory"]
                    + left
                    + right
                )
                jacobian[row, before * count + index] -= control["memory"]
                jacobian[row, after * count + index] -= control["memory"]
                jacobian[row, phase * count + previous] -= left
                jacobian[row, phase * count + following] -= right
        if np.max(np.abs(residual)) < 1e-13:
            break
        opening += np.linalg.solve(jacobian, -residual).reshape(phases, count)
    else:
        raise AssertionError("reference periodic solve did not converge")

    states: list[list[dict[str, float | str]]] = []
    for phase in range(phases):
        phase_states = []
        for index, fracture in enumerate(fractures):
            value = opening[phase, index]
            salinity = fracture["salinity_ppt"]
            gas = fracture["gas_ppm"]
            water = (
                value**3
                * math.sqrt(max(0.0, control["ocean_pressure"] - fracture["depth_km"]))
                / (fracture["viscosity"] * (1.0 + salinity / 100.0))
            )
            vapor = min(
                0.95,
                max(
                    0.0,
                    (control["temperature"] - 273.15 + 0.055 * salinity) / 18.0
                    + gas / 8000.0,
                ),
            )
            m18 = water * vapor
            m44 = m18 * gas / 4000.0
            brightness = (
                water
                * (1.0 - vapor)
                * (1.0 + salinity / 50.0)
                * (120.0 + 280.0 * vapor + 0.01 * gas)
                / math.sqrt(226000.0)
            )
            phase_states.append(
                {
                    "phase": float(phase),
                    "fracture": fracture["id"],
                    "opening_mm": value,
                    "water_flux": water,
                    "m18": m18,
                    "m44": m44,
                    "brightness": brightness,
                }
            )
        states.append(phase_states)
    return states, drives, edges


def _inverse_terms(
    states: list[list[dict[str, float | str]]],
    observations: list[dict[str, float]],
    control: dict[str, float],
) -> tuple[np.ndarray, np.ndarray]:
    count = len(states[0])
    normal = np.eye(count) * control["ridge"]
    projected = np.zeros(count)
    for observation in observations:
        phase = int(observation["phase"])
        design = np.array(
            [
                [row[signal] for row in states[phase]]
                for signal in ("m18", "m44", "brightness")
            ],
            dtype=float,
        )
        measured = np.array(
            [observation[signal] for signal in ("m18", "m44", "brightness")]
        )
        sigmas = np.array(
            [
                observation[sigma]
                for sigma in ("sigma_m18", "sigma_m44", "sigma_brightness")
            ]
        )
        covariance = np.outer(sigmas, sigmas) * control["signal_rho"]
        np.fill_diagonal(covariance, sigmas**2)
        precision = np.linalg.inv(covariance)
        normal += design.T @ precision @ design
        projected += design.T @ precision @ measured
    return normal, projected


def _objective(
    weights: np.ndarray,
    normal: np.ndarray,
    projected: np.ndarray,
    control: dict[str, float],
) -> float:
    differences = weights - np.roll(weights, -1)
    return float(
        weights @ normal @ weights
        - 2.0 * projected @ weights
        + control["tv"]
        * np.sum(np.sqrt(differences**2 + control["tv_eps"] ** 2))
    )


def _gradient(
    weights: np.ndarray,
    normal: np.ndarray,
    projected: np.ndarray,
    control: dict[str, float],
) -> np.ndarray:
    gradient = 2.0 * normal @ weights - 2.0 * projected
    for index in range(len(weights)):
        following = (index + 1) % len(weights)
        difference = weights[index] - weights[following]
        value = (
            control["tv"]
            * difference
            / math.sqrt(difference**2 + control["tv_eps"] ** 2)
        )
        gradient[index] += value
        gradient[following] -= value
    return gradient


def _hessian(
    weights: np.ndarray, normal: np.ndarray, control: dict[str, float]
) -> np.ndarray:
    hessian = 2.0 * normal.copy()
    for index in range(len(weights)):
        following = (index + 1) % len(weights)
        difference = weights[index] - weights[following]
        curvature = (
            control["tv"]
            * control["tv_eps"] ** 2
            / (difference**2 + control["tv_eps"] ** 2) ** 1.5
        )
        hessian[index, index] += curvature
        hessian[following, following] += curvature
        hessian[index, following] -= curvature
        hessian[following, index] -= curvature
    return hessian


def _solve_weights(
    states: list[list[dict[str, float | str]]],
    observations: list[dict[str, float]],
    control: dict[str, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    normal, projected = _inverse_terms(states, observations, control)
    count = normal.shape[0]
    best_value = math.inf
    best_weights: np.ndarray | None = None
    for mask in range(1, 1 << count):
        active = np.array([index for index in range(count) if mask & (1 << index)])
        weights = np.zeros(count)
        weights[active] = control["source_total"] / len(active)
        multiplier = 0.0
        for _ in range(100):
            residual = np.append(
                _gradient(weights, normal, projected, control)[active] + multiplier,
                np.sum(weights) - control["source_total"],
            )
            if np.max(np.abs(residual)) < 1e-11:
                break
            hessian = _hessian(weights, normal, control)
            size = len(active)
            kkt = np.block(
                [
                    [hessian[np.ix_(active, active)], np.ones((size, 1))],
                    [np.ones((1, size)), np.zeros((1, 1))],
                ]
            )
            delta = np.linalg.solve(kkt, -residual)
            step = 1.0
            for position, index in enumerate(active):
                if delta[position] < 0.0:
                    step = min(step, -0.99 * weights[index] / delta[position])
            weights[active] += step * delta[:-1]
            multiplier += step * delta[-1]
        else:
            continue
        if np.min(weights[active]) < -1e-10:
            continue
        value = _objective(weights, normal, projected, control)
        if value < best_value:
            best_value = value
            best_weights = weights.copy()
    if best_weights is None:
        raise AssertionError("reference inverse solve failed")
    return best_weights, normal, projected


def _design_portfolio(
    states: list[list[dict[str, float | str]]],
    candidates: list[dict[str, float | str]],
    control: dict[str, float],
) -> tuple[list[dict[str, float | str]], dict[str, float]]:
    count = len(states[0])
    rows = []
    contributions = []
    for candidate in candidates:
        phase = int(candidate["phase"])
        attenuation = (
            math.exp(-candidate["altitude_km"] / 180.0) / candidate["speed_kms"]
        )
        basis = (
            np.array(
                [
                    [row[signal] for row in states[phase]]
                    for signal in ("m18", "m44", "brightness")
                ],
                dtype=float,
            )
            * attenuation
        )
        contribution = basis.T @ basis / control["design_noise"] ** 2
        contributions.append(contribution)
        dose = (
            sum(row["water_flux"] for row in states[phase])
            * math.exp(-candidate["altitude_km"] / 120.0)
            / candidate["speed_kms"]
        )
        rows.append(
            {
                "candidate": candidate["candidate"],
                "score": float(np.linalg.slogdet(np.eye(count) + contribution)[1]),
                "dose": dose,
                "feasible": float(dose <= candidate["dose_limit"]),
                "selected": 0.0,
            }
        )

    best_score = -math.inf
    best_combo: tuple[int, ...] | None = None
    best_dose = 0.0
    for combo in itertools.combinations(
        range(len(candidates)), int(control["portfolio_size"])
    ):
        if not all(rows[index]["feasible"] for index in combo):
            continue
        total_dose = sum(float(rows[index]["dose"]) for index in combo)
        if total_dose > control["portfolio_dose"]:
            continue
        separated = True
        for first, second in itertools.combinations(combo, 2):
            difference = abs(candidates[first]["phase"] - candidates[second]["phase"])
            circular = min(difference, control["phases"] - difference)
            separated &= circular >= control["phase_gap"]
        if not separated:
            continue
        information = np.eye(count) + sum(
            (contributions[index] for index in combo), np.zeros((count, count))
        )
        score = float(np.linalg.slogdet(information)[1])
        if score > best_score:
            best_score = score
            best_combo = combo
            best_dose = total_dose
    if best_combo is None:
        raise AssertionError("reference portfolio has no feasible combination")
    for index in best_combo:
        rows[index]["selected"] = 1.0
    return rows, {"score": best_score, "total_dose": best_dose}


def _reference(
    control_row: str = CONTROL_ROW,
    fracture_rows: list[str] | None = None,
    observation_rows: list[str] | None = None,
    candidate_rows: list[str] | None = None,
) -> tuple[
    list[list[dict[str, float | str]]],
    np.ndarray,
    np.ndarray,
    np.ndarray,
    list[dict[str, float | str]],
    dict[str, float],
]:
    control, fractures, observations, candidates = _inputs(
        control_row, fracture_rows, observation_rows, candidate_rows
    )
    states, drives, edges = _solve_states(control, fractures)
    weights, _, _ = _solve_weights(states, observations, control)
    flybys, portfolio = _design_portfolio(states, candidates, control)
    return states, drives, edges, weights, flybys, portfolio


def _table(database: Path, query: str) -> list[sqlite3.Row]:
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(query).fetchall()


@pytest.fixture(scope="module", autouse=True)
def _prepare_baseline() -> None:
    """prepare verifier owned inputs and regenerate the documented database."""
    _write_case(BASE_ROOT)
    BASE_OUTPUT.mkdir(parents=True, exist_ok=True)
    BASE_DB.unlink(missing_ok=True)
    result = _run(BASE_ROOT, BASE_OUTPUT)
    assert result.returncode == 0, result.stderr
    assert BASE_DB.is_file()


def test_entrypoint_writes_database_inside_the_output_directory() -> None:
    """the janet command writes exactly the documented sqlite schemas."""
    objects = {
        (row["type"], row["name"], row["tbl_name"])
        for row in _table(
            BASE_DB,
            "SELECT type, name, tbl_name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
        )
    }
    assert objects == {("table", table, table) for table in EXPECTED_SCHEMA}
    for table, expected in EXPECTED_SCHEMA.items():
        actual = _table(BASE_DB, f"PRAGMA table_info({table})")
        assert len(actual) == len(expected)
        for column, specification in zip(actual, expected, strict=True):
            cid, name, data_type, not_null, default, primary_key = specification
            assert column["cid"] == cid
            assert column["name"] == name
            assert column["type"].upper() == data_type
            if not_null:
                assert column["notnull"] == 1
            assert column["dflt_value"] == default
            assert column["pk"] == primary_key
    assert _table(BASE_DB, "SELECT count(*) AS n FROM state")[0]["n"] == 120
    assert _table(BASE_DB, "SELECT count(*) AS n FROM reconstruction")[0]["n"] == 5
    assert _table(BASE_DB, "SELECT count(*) AS n FROM flyby")[0]["n"] == 6
    assert _table(BASE_DB, "SELECT count(*) AS n FROM portfolio")[0]["n"] == 1


def test_periodic_space_time_openings_match_reference_and_residual() -> None:
    """openings solve the coupled cyclic fracture and cyclic phase equations."""
    expected, drives, edges, _, _, _ = _reference()
    control, fractures, _, _ = _inputs()
    actual = _table(
        BASE_DB,
        "SELECT phase, fracture, opening_mm FROM state ORDER BY phase, fracture",
    )
    lookup = {(int(row["phase"]), row["fracture"]): row["opening_mm"] for row in actual}
    for phase_states in expected:
        for row in phase_states:
            value = lookup[(int(row["phase"]), row["fracture"])]
            assert value == pytest.approx(row["opening_mm"], rel=2e-10, abs=1e-12)

    residuals = []
    phases = int(control["phases"])
    count = len(fractures)
    for phase in range(phases):
        for index, fracture in enumerate(fractures):
            previous = (index - 1) % count
            following = (index + 1) % count
            value = lookup[(phase, fracture["id"])]
            residuals.append(
                value
                + control["cubic"] * fracture["viscosity"] * value**3
                + control["memory"]
                * (
                    2.0 * value
                    - lookup[((phase - 1) % phases, fracture["id"])]
                    - lookup[((phase + 1) % phases, fracture["id"])]
                )
                + edges[phase, previous]
                * (value - lookup[(phase, fractures[previous]["id"])])
                + edges[phase, index]
                * (value - lookup[(phase, fractures[following]["id"])])
                - max(0.0, drives[phase, index])
            )
    assert max(abs(value) for value in residuals) < 1e-11


def test_plume_observables_match_reference() -> None:
    """water and all three plume signals use the documented physical laws."""
    expected, _, _, _, _, _ = _reference()
    actual = _table(BASE_DB, "SELECT * FROM state ORDER BY phase, fracture")
    lookup = {(int(row["phase"]), row["fracture"]): row for row in actual}
    for phase_states in expected:
        for expected_row in phase_states:
            row = lookup[(int(expected_row["phase"]), expected_row["fracture"])]
            for column in ("water_flux", "m18", "m44", "brightness"):
                assert row[column] == pytest.approx(
                    expected_row[column], rel=2e-10, abs=1e-12
                )


def test_reconstruction_is_correlated_tv_global_simplex_optimum() -> None:
    """weights attain the unique correlated total variation simplex optimum."""
    states, _, _, expected_weights, _, _ = _reference()
    control, _, observations, _ = _inputs()
    normal, projected = _inverse_terms(states, observations, control)
    actual = _table(BASE_DB, "SELECT fracture, weight FROM reconstruction")
    by_name = {row["fracture"]: row["weight"] for row in actual}
    weights = np.array([by_name[row.split(",", 1)[0]] for row in FRACTURE_ROWS])
    assert weights == pytest.approx(expected_weights, rel=2e-8, abs=2e-10)
    assert np.min(weights) >= 0.0
    assert np.sum(weights) == pytest.approx(control["source_total"], abs=1e-10)
    gradient = _gradient(weights, normal, projected, control)
    active = weights > 1e-9
    multiplier = -float(np.mean(gradient[active]))
    assert np.max(np.abs(gradient[active] + multiplier)) < 2e-7
    assert np.min(gradient[~active] + multiplier) >= -2e-7


def test_flyby_portfolio_is_global_feasible_optimum() -> None:
    """candidate metrics and the selected portfolio match the constrained optimum."""
    _, _, _, _, expected_rows, expected_portfolio = _reference()
    actual = _table(BASE_DB, "SELECT * FROM flyby ORDER BY candidate")
    expected = {row["candidate"]: row for row in expected_rows}
    assert sum(row["selected"] for row in actual) == 3
    assert {row["feasible"] for row in actual} == {0, 1}
    for row in actual:
        reference = expected[row["candidate"]]
        assert row["score"] == pytest.approx(reference["score"], rel=2e-9)
        assert row["dose"] == pytest.approx(reference["dose"], rel=2e-9)
        assert row["feasible"] == reference["feasible"]
        assert row["selected"] == reference["selected"]
    portfolio = _table(BASE_DB, "SELECT * FROM portfolio")[0]
    assert portfolio["score"] == pytest.approx(expected_portfolio["score"], rel=2e-9)
    assert portfolio["total_dose"] == pytest.approx(
        expected_portfolio["total_dose"], rel=2e-9
    )


def test_identical_inputs_replace_database_deterministically() -> None:
    """identical reruns replace the database with identical bytes and values."""
    before = BASE_DB.read_bytes()
    rows_before = [
        tuple(row) for row in _table(BASE_DB, "SELECT * FROM state ORDER BY phase, fracture")
    ]
    result = _run(BASE_ROOT, BASE_OUTPUT)
    assert result.returncode == 0, result.stderr
    rows_after = [
        tuple(row) for row in _table(BASE_DB, "SELECT * FROM state ORDER BY phase, fracture")
    ]
    assert rows_after == rows_before
    assert BASE_DB.read_bytes() == before


def test_changed_inputs_recompute_every_optimization_stage() -> None:
    """changed physics regularization covariance and mission limits are recomputed."""
    mutated_control = (
        "18,0.0061,8.1,270.2,0.024,0.55,0.07,0.11,0.03,0.50,1.15,0.042,"
        "-0.15,2,0.25,5"
    )
    mutated_fractures = [
        "baghdad,20.5,6.6,1.42,0.39,0.21,0.22,29.0,1750.0",
        *FRACTURE_ROWS[1:],
    ]
    mutated_observations = []
    for index, row in enumerate(OBS_ROWS[:15]):
        cells = row.split(",")
        cells[0] = str(index % 18)
        cells[1] = str(float(cells[1]) + 0.0007 * (1 + index % 3))
        cells[2] = str(float(cells[2]) - 0.0004 * (1 + index % 2))
        cells[3] = str(float(cells[3]) * 1.06)
        cells[4:] = ["0.027", "0.021", "0.034"]
        mutated_observations.append(",".join(cells))
    mutated_candidates = [
        "orbiter-a,1,48,7.2,0.20",
        "orbiter-b,4,72,5.9,0.20",
        "orbiter-c,7,84,5.2,0.20",
        "orbiter-d,10,38,7.7,0.20",
        "orbiter-e,13,108,4.5,0.20",
        "orbiter-f,16,61,6.4,0.20",
    ]
    root = Path("/tmp/plume_mutated_input")
    output = Path("/tmp/plume_mutated/nested/output")
    shutil.rmtree(Path("/tmp/plume_mutated"), ignore_errors=True)
    _write_case(
        root,
        mutated_control,
        mutated_fractures,
        mutated_observations,
        mutated_candidates,
    )
    result = _run(root, output)
    assert result.returncode == 0, result.stderr
    database = output / "plume.db"
    expected_states, _, _, expected_weights, expected_flybys, expected_portfolio = (
        _reference(
            mutated_control,
            mutated_fractures,
            mutated_observations,
            mutated_candidates,
        )
    )
    state = _table(database, "SELECT * FROM state")
    state_map = {(row["phase"], row["fracture"]): row for row in state}
    for phase_states in expected_states:
        for expected in phase_states:
            row = state_map[(expected["phase"], expected["fracture"])]
            for column in ("opening_mm", "water_flux", "m18", "m44", "brightness"):
                assert row[column] == pytest.approx(expected[column], rel=2e-9)
    weights = _table(database, "SELECT fracture, weight FROM reconstruction")
    weight_map = {row["fracture"]: row["weight"] for row in weights}
    for index, fracture in enumerate(mutated_fractures):
        assert weight_map[fracture.split(",", 1)[0]] == pytest.approx(
            expected_weights[index], rel=2e-8, abs=2e-10
        )
    flyby_map = {
        row["candidate"]: row for row in _table(database, "SELECT * FROM flyby")
    }
    for expected in expected_flybys:
        row = flyby_map[expected["candidate"]]
        assert row["score"] == pytest.approx(expected["score"], rel=2e-9)
        assert row["dose"] == pytest.approx(expected["dose"], rel=2e-9)
        assert row["feasible"] == expected["feasible"]
        assert row["selected"] == expected["selected"]
    portfolio = _table(database, "SELECT * FROM portfolio")[0]
    assert portfolio["score"] == pytest.approx(expected_portfolio["score"], rel=2e-9)
    assert portfolio["total_dose"] == pytest.approx(
        expected_portfolio["total_dose"], rel=2e-9
    )


def test_invalid_control_csv_inputs_fail() -> None:
    """control csv rejects incomplete nonnumeric repeated and invalid rho values."""
    root = Path("/tmp/plume_invalid_input")
    output = Path("/tmp/plume_invalid_output")
    _write_case(root)
    (root / "control.csv").write_text(
        "phases,eccentricity\n24,0.0047\n", encoding="utf-8"
    )
    assert _run(root, output).returncode != 0

    _write_case(root, control_row=CONTROL_ROW.replace("24,", "not-a-number,", 1))
    assert _run(root, output).returncode != 0

    _write_case(root)
    (root / "control.csv").write_text(CONTROL_HEADER + "\n", encoding="utf-8")
    assert _run(root, output).returncode != 0

    for invalid_control in (
        CONTROL_ROW.replace("24,", "24.5,", 1),
        CONTROL_ROW.replace("0.25,3,0.20", "0.25,2.5,0.20", 1),
    ):
        _write_case(root, control_row=invalid_control)
        assert _run(root, output).returncode != 0

    _write_case(root)
    with (root / "control.csv").open("a", encoding="utf-8") as stream:
        stream.write(CONTROL_ROW + "\n")
    assert _run(root, output).returncode != 0

    for rho in ("1.0", "-0.5"):
        invalid_rho = CONTROL_ROW.replace("0.25,3,", f"{rho},3,", 1)
        _write_case(root, control_row=invalid_rho)
        assert _run(root, output).returncode != 0


def test_invalid_fracture_csv_inputs_fail() -> None:
    """fracture csv rejects incomplete nonnumeric and duplicate id values."""
    root = Path("/tmp/plume_invalid_input")
    output = Path("/tmp/plume_invalid_output")
    _write_case(root)
    (root / "fractures.csv").write_text("id,shell_km\nbaghdad,24\n", encoding="utf-8")
    assert _run(root, output).returncode != 0

    nonnumeric = [
        FRACTURE_ROWS[0].replace("24.0", "not-a-number", 1),
        *FRACTURE_ROWS[1:],
    ]
    _write_case(root, fracture_rows=nonnumeric)
    assert _run(root, output).returncode != 0

    duplicates = [FRACTURE_ROWS[0], FRACTURE_ROWS[0], *FRACTURE_ROWS[1:]]
    _write_case(root, fracture_rows=duplicates)
    assert _run(root, output).returncode != 0


def test_invalid_observation_csv_inputs_fail() -> None:
    """observation csv rejects incomplete nonnumeric and out of grid values."""
    root = Path("/tmp/plume_invalid_input")
    output = Path("/tmp/plume_invalid_output")
    _write_case(root)
    observation = root / "observations" / "obs_00.csv"
    observation.write_text("phase,m18\n0,0.2\n", encoding="utf-8")
    assert _run(root, output).returncode != 0

    _write_case(root)
    observation = root / "observations" / "obs_00.csv"
    observation.write_text(
        f"{OBS_HEADER}\n{OBS_ROWS[0].replace('0.00350515231936326', 'bad', 1)}\n",
        encoding="utf-8",
    )
    assert _run(root, output).returncode != 0

    _write_case(root, observation_rows=[OBS_ROWS[0].replace("0,", "24,", 1)])
    assert _run(root, output).returncode != 0

    _write_case(root, observation_rows=[OBS_ROWS[0].replace("0,", "0.5,", 1)])
    assert _run(root, output).returncode != 0


def test_invalid_candidate_csv_inputs_fail() -> None:
    """candidate csv rejects incomplete nonnumeric and out of grid values."""
    root = Path("/tmp/plume_invalid_input")
    output = Path("/tmp/plume_invalid_output")
    _write_case(root)
    (root / "candidates.csv").write_text(
        "candidate,phase\norbiter-a,2\n", encoding="utf-8"
    )
    assert _run(root, output).returncode != 0

    nonnumeric = [
        CANDIDATE_ROWS[0].replace(",42,", ",bad,", 1),
        *CANDIDATE_ROWS[1:],
    ]
    _write_case(root, candidate_rows=nonnumeric)
    assert _run(root, output).returncode != 0

    outside_candidate = [
        CANDIDATE_ROWS[0].replace(",2,", ",24,", 1),
        *CANDIDATE_ROWS[1:],
    ]
    _write_case(root, candidate_rows=outside_candidate)
    assert _run(root, output).returncode != 0

    fractional_candidate = [
        CANDIDATE_ROWS[0].replace(",2,", ",2.5,", 1),
        *CANDIDATE_ROWS[1:],
    ]
    _write_case(root, candidate_rows=fractional_candidate)
    assert _run(root, output).returncode != 0
