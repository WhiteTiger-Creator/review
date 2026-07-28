"""Behavioral verification for the penalized hierarchical profile fit."""

from __future__ import annotations

import math
import pathlib
import shutil
import sqlite3
import subprocess

import numpy as np
import pytest
import scipy.optimize

DATABASE = pathlib.Path("/app/data/soil.sqlite")
COMMAND = pathlib.Path("/app/bin/soilfit")
PARAMETERS = ("k0", "cue", "v")
INPUT_TABLES = ("layers", "forcing", "observations", "bounds", "penalty_grid")
OUTPUT_TABLES = ("fit_summary", "cv_scores", "fit_limits", "plot_fit", "profile")
LAMBDA14 = math.log(2.0) / 5730.0
THRESHOLD = 3.841459


def rows(database: pathlib.Path, query: str) -> list[tuple]:
    """return query rows from a database."""
    with sqlite3.connect(database) as connection:
        return connection.execute(query).fetchall()


def snapshot_inputs(database: pathlib.Path) -> dict[str, list[tuple]]:
    """capture all input values in deterministic primary-key order."""
    order = {
        "layers": "plot, depth",
        "forcing": "plot",
        "observations": "plot, depth",
        "bounds": "parameter",
        "penalty_grid": "weight",
    }
    return {
        table: rows(database, f"SELECT * FROM {table} ORDER BY {order[table]}")
        for table in INPUT_TABLES
    }


def snapshot_outputs(database: pathlib.Path) -> dict[str, list[tuple]]:
    """capture every generated table for atomic failure checks."""
    return {
        table: rows(database, f"SELECT * FROM {table} ORDER BY rowid")
        for table in OUTPUT_TABLES
    }


def load_problem(database: pathlib.Path) -> tuple[dict, dict, list[float]]:
    """load model inputs without relying on generated output tables."""
    problem: dict[str, dict] = {}
    with sqlite3.connect(database) as connection:
        bounds = {
            name: (float(lower), float(upper))
            for name, lower, upper in connection.execute(
                "SELECT parameter, lower, upper FROM bounds",
            )
        }
        weights = sorted(
            float(weight)
            for (weight,) in connection.execute("SELECT weight FROM penalty_grid")
        )
        for plot, moisture_scale, oxygen_scale in connection.execute(
            "SELECT plot, moisture_scale, oxygen_scale FROM forcing",
        ):
            problem[str(plot)] = {
                "moisture_scale": float(moisture_scale),
                "oxygen_scale": float(oxygen_scale),
            }
        for record in connection.execute(
            "SELECT plot, depth, temp, moisture, clay, input, f_input "
            "FROM layers ORDER BY plot, depth",
        ):
            plot = str(record[0])
            problem[plot].setdefault("layers", []).append(
                np.asarray(record[1:], dtype=float),
            )
        for record in connection.execute(
            "SELECT plot, depth, carbon, respiration, f14c, sigma_c, sigma_r, "
            "sigma_f, fold FROM observations ORDER BY plot, depth",
        ):
            plot = str(record[0])
            problem[plot].setdefault("observations", []).append(
                np.asarray(record[1:8], dtype=float),
            )
            problem[plot].setdefault("folds", []).append(int(record[8]))
    for plot in problem.values():
        plot["layers"] = np.vstack(plot["layers"])
        plot["observations"] = np.vstack(plot["observations"])
        plot["folds"] = np.asarray(plot["folds"], dtype=int)
    return problem, bounds, weights


def forward_plot(
    plot: dict, parameters: np.ndarray, input_scale: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """independently solve carbon, respiration, isotope, and age balances."""
    k0, cue, mixing = parameters
    layer = plot["layers"]
    modifier = (
        np.exp(0.069314718 * (layer[:, 1] - 10.0))
        * layer[:, 2]
        * plot["moisture_scale"]
        * plot["oxygen_scale"]
        * (1.0 - 0.35 * layer[:, 3])
    )
    decay = k0 * modifier
    count = len(layer)
    balance = np.diag(decay)
    for index in range(count - 1):
        balance[index, index] += mixing
        balance[index + 1, index + 1] += mixing
        balance[index, index + 1] -= mixing
        balance[index + 1, index] -= mixing
    carbon = np.linalg.solve(balance, input_scale * layer[:, 4])
    isotope = np.linalg.solve(
        balance + LAMBDA14 * np.eye(count),
        input_scale * layer[:, 4] * layer[:, 5],
    )
    age_moment = np.linalg.solve(balance, carbon)
    respiration = (1.0 - cue) * decay * carbon
    return carbon, respiration, isotope / carbon, age_moment / carbon


def plot_effect(
    plot: dict,
    bounds: dict,
    parameters: np.ndarray,
    weight: float,
    mask: np.ndarray,
) -> float:
    """profile one plot effect in closed form over the training rows."""
    carbon, respiration, _, _ = forward_plot(plot, parameters, 1.0)
    observed = plot["observations"]
    numerator = weight
    denominator = weight
    numerator += np.sum((carbon * observed[:, 1] / observed[:, 4] ** 2)[mask])
    numerator += np.sum((respiration * observed[:, 2] / observed[:, 5] ** 2)[mask])
    denominator += np.sum((carbon**2 / observed[:, 4] ** 2)[mask])
    denominator += np.sum((respiration**2 / observed[:, 5] ** 2)[mask])
    return float(np.clip(numerator / denominator, *bounds["input_scale"]))


def residual_sum(
    plot: dict, parameters: np.ndarray, input_scale: float, mask: np.ndarray,
) -> float:
    """standardized squared misfit over a chosen row subset."""
    carbon, respiration, f14c, _ = forward_plot(plot, parameters, input_scale)
    observed = plot["observations"]
    total = np.sum((((carbon - observed[:, 1]) / observed[:, 4]) ** 2)[mask])
    total += np.sum((((respiration - observed[:, 2]) / observed[:, 5]) ** 2)[mask])
    total += np.sum((((f14c - observed[:, 3]) / observed[:, 6]) ** 2)[mask])
    return float(total)


def training_masks(problem: dict, holdout: int | None) -> dict[str, np.ndarray]:
    """rows kept for training once one fold is withheld."""
    if holdout is None:
        return {
            name: np.ones(len(plot["folds"]), dtype=bool)
            for name, plot in problem.items()
        }
    return {name: plot["folds"] != holdout for name, plot in problem.items()}


def objective_value(
    problem: dict,
    bounds: dict,
    parameters: np.ndarray,
    weight: float,
    masks: dict[str, np.ndarray],
) -> float:
    """penalized training criterion at one parameter triple."""
    total = 0.0
    for name, plot in problem.items():
        effect = plot_effect(plot, bounds, parameters, weight, masks[name])
        total += weight * (effect - 1.0) ** 2
        total += residual_sum(plot, parameters, effect, masks[name])
    return total


def minimize_criterion(
    problem: dict, bounds: dict, weight: float, masks: dict[str, np.ndarray],
) -> tuple[np.ndarray, float]:
    """search the parameter box with an independent simplex solver."""
    box = [bounds[name] for name in PARAMETERS]
    starts = [
        np.asarray([low + share * (high - low) for low, high in box])
        for share in (0.25, 0.5, 0.75)
    ]
    results = [
        scipy.optimize.minimize(
            lambda point: objective_value(problem, bounds, point, weight, masks),
            start,
            method="Nelder-Mead",
            bounds=box,
            options={"xatol": 1e-11, "fatol": 1e-10, "maxiter": 5000},
        )
        for start in starts
    ]
    best = min(results, key=lambda item: item.fun)
    assert best.success, best.message
    return np.asarray(best.x), float(best.fun)


def cross_validate(
    problem: dict, bounds: dict, weights: list[float],
) -> dict[float, dict]:
    """score every candidate weight on withheld rows and on all rows."""
    folds = sorted({int(fold) for plot in problem.values() for fold in plot["folds"]})
    curve: dict[float, dict] = {}
    for weight in weights:
        held = 0.0
        for fold in folds:
            masks = training_masks(problem, fold)
            parameters, _ = minimize_criterion(problem, bounds, weight, masks)
            for name, plot in problem.items():
                effect = plot_effect(plot, bounds, parameters, weight, masks[name])
                held += residual_sum(plot, parameters, effect, plot["folds"] == fold)
        full = training_masks(problem, None)
        estimate, train = minimize_criterion(problem, bounds, weight, full)
        curve[weight] = {
            "heldout": held,
            "train": train,
            "estimate": estimate,
        }
    return curve


def choose_weight(curve: dict[float, dict]) -> float:
    """smallest weight among those with the lowest withheld loss."""
    best = min(sorted(curve), key=lambda weight: curve[weight]["heldout"])
    return float(best)


def profile_minimum(
    problem: dict,
    bounds: dict,
    weight: float,
    estimate: np.ndarray,
    index: int,
    value: float,
) -> float:
    """minimize the criterion with one parameter pinned."""
    free = [position for position in range(3) if position != index]
    box = [bounds[name] for name in PARAMETERS]
    masks = training_masks(problem, None)

    def reduced(point: np.ndarray) -> float:
        parameters = estimate.copy()
        parameters[index] = value
        parameters[free] = point
        return objective_value(problem, bounds, parameters, weight, masks)

    result = scipy.optimize.minimize(
        reduced,
        estimate[free],
        method="Nelder-Mead",
        bounds=[box[position] for position in free],
        options={"xatol": 2e-10, "fatol": 1e-9, "maxiter": 3000},
    )
    assert result.success, result.message
    return float(result.fun)


def reference_fit(database: pathlib.Path, *, limits: bool = True) -> dict:
    """rebuild the selection, the fit, and its interval endpoints independently."""
    problem, bounds, weights = load_problem(database)
    curve = cross_validate(problem, bounds, weights)
    weight = choose_weight(curve)
    estimate = curve[weight]["estimate"]
    minimum = curve[weight]["train"]
    reference = {
        "problem": problem,
        "bounds": bounds,
        "weights": weights,
        "curve": curve,
        "weight": weight,
        "estimate": estimate,
        "objective": minimum,
        "effects": {
            name: plot_effect(
                plot, bounds, estimate, weight, training_masks(problem, None)[name],
            )
            for name, plot in problem.items()
        },
    }
    if not limits:
        return reference
    target = minimum + THRESHOLD
    endpoints: dict[str, tuple[float, float]] = {}
    for index, name in enumerate(PARAMETERS):
        found = []
        for edge in bounds[name]:
            if profile_minimum(
                problem, bounds, weight, estimate, index, edge,
            ) <= target:
                found.append(edge)
                continue
            root = scipy.optimize.root_scalar(
                lambda value, index=index: profile_minimum(
                    problem, bounds, weight, estimate, index, value,
                ) - target,
                bracket=sorted((edge, estimate[index])),
                xtol=1e-10,
            )
            assert root.converged
            found.append(float(root.root))
        endpoints[name] = (found[0], found[1])
    reference["limits"] = endpoints
    return reference


def run_command(database: pathlib.Path) -> subprocess.CompletedProcess:
    """invoke the provided runner on one database."""
    return subprocess.run(
        [str(COMMAND), str(database)], capture_output=True, text=True, check=False,
    )


def reported_fit(database: pathlib.Path) -> dict:
    """read the single reported summary row."""
    result = rows(
        database, "SELECT k0, cue, v, penalty, objective FROM fit_summary",
    )
    assert len(result) == 1
    values = [float(item) for item in result[0]]
    return {
        "estimate": np.asarray(values[:3]),
        "penalty": values[3],
        "objective": values[4],
    }


@pytest.fixture(scope="session")
def baseline() -> dict:
    """regenerate baseline outputs so every assertion exercises the runner."""
    before = snapshot_inputs(DATABASE)
    with sqlite3.connect(DATABASE) as connection:
        for table in OUTPUT_TABLES:
            connection.execute(f"DROP TABLE IF EXISTS {table}")
    completed = run_command(DATABASE)
    assert completed.returncode == 0, completed.stderr
    return {"inputs": before, "reference": reference_fit(DATABASE)}


def test_result_tables_are_regenerated_with_documented_fields(baseline: dict) -> None:
    """the runner creates each result table with its named fields and row count."""
    del baseline
    expected_columns = {
        "fit_summary": {"k0", "cue", "v", "penalty", "objective"},
        "cv_scores": {"weight", "heldout_loss", "train_loss"},
        "fit_limits": {"parameter", "lower", "upper"},
        "plot_fit": {"plot", "input_scale"},
        "profile": {
            "plot",
            "depth",
            "carbon_hat",
            "respiration_hat",
            "f14c_hat",
            "mean_age",
        },
    }
    expected_counts = {
        "fit_summary": 1,
        "cv_scores": 5,
        "fit_limits": 3,
        "plot_fit": 8,
        "profile": 24,
    }
    with sqlite3.connect(DATABASE) as connection:
        for table, names in expected_columns.items():
            columns = {
                row[1] for row in connection.execute(f"PRAGMA table_info({table})")
            }
            assert columns == names
        for table, count in expected_counts.items():
            found = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert found == count


def test_cross_validation_curve_matches_an_independent_refit(baseline: dict) -> None:
    """every candidate weight reports the withheld and full-data losses it earns."""
    reference = baseline["reference"]
    reported = {
        float(weight): (float(heldout), float(train))
        for weight, heldout, train in rows(
            DATABASE, "SELECT weight, heldout_loss, train_loss FROM cv_scores",
        )
    }
    assert sorted(reported) == pytest.approx(reference["weights"])
    for weight, scores in reference["curve"].items():
        assert reported[weight][0] == pytest.approx(
            scores["heldout"], rel=0.005, abs=0.02,
        )
        assert reported[weight][1] == pytest.approx(
            scores["train"], rel=0.005, abs=0.02,
        )


def test_selected_penalty_minimizes_the_withheld_loss(baseline: dict) -> None:
    """the reported penalty is the candidate with the lowest cross validated loss."""
    reference = baseline["reference"]
    reported = reported_fit(DATABASE)
    assert reported["penalty"] == pytest.approx(reference["weight"], rel=1e-9)
    losses = {
        float(weight): float(loss)
        for weight, loss in rows(DATABASE, "SELECT weight, heldout_loss FROM cv_scores")
    }
    lowest = min(sorted(losses), key=lambda weight: losses[weight])
    assert lowest == pytest.approx(reported["penalty"], rel=1e-9)


def test_parameters_minimize_the_penalized_criterion(baseline: dict) -> None:
    """the reported triple and objective agree with an independent global search."""
    reference = baseline["reference"]
    reported = reported_fit(DATABASE)
    assert np.allclose(
        reported["estimate"], reference["estimate"], rtol=0.005, atol=2e-7,
    )
    assert reported["objective"] == pytest.approx(
        reference["objective"], rel=0.005, abs=0.02,
    )
    replay = objective_value(
        reference["problem"],
        reference["bounds"],
        reported["estimate"],
        reported["penalty"],
        training_masks(reference["problem"], None),
    )
    assert replay == pytest.approx(reported["objective"], abs=0.02)


def test_plot_effects_are_penalized_optima(baseline: dict) -> None:
    """each plot effect is the shrunken optimum implied by the reported fit."""
    reference = baseline["reference"]
    reported = reported_fit(DATABASE)
    effects = dict(rows(DATABASE, "SELECT plot, input_scale FROM plot_fit"))
    assert set(effects) == set(reference["problem"])
    masks = training_masks(reference["problem"], None)
    for name, plot in reference["problem"].items():
        expected = plot_effect(
            plot, reference["bounds"], reported["estimate"], reported["penalty"],
            masks[name],
        )
        assert float(effects[name]) == pytest.approx(expected, rel=5e-4, abs=1e-7)


def test_carbon_respiration_and_radiocarbon_predictions_replay(
    baseline: dict,
) -> None:
    """profile rows reproduce all three balances at the reported fit."""
    reference = baseline["reference"]
    reported = reported_fit(DATABASE)
    effects = dict(rows(DATABASE, "SELECT plot, input_scale FROM plot_fit"))
    predicted = {
        (plot, float(depth)): np.asarray((carbon, respiration, f14c), dtype=float)
        for plot, depth, carbon, respiration, f14c in rows(
            DATABASE,
            "SELECT plot, depth, carbon_hat, respiration_hat, f14c_hat FROM profile",
        )
    }
    for name, plot in reference["problem"].items():
        expected = forward_plot(
            plot, reported["estimate"], float(effects[name]),
        )
        for index, depth in enumerate(plot["layers"][:, 0]):
            values = np.asarray(
                (expected[0][index], expected[1][index], expected[2][index]),
            )
            assert np.allclose(
                predicted[(name, float(depth))], values, rtol=5e-4, atol=2e-8,
            )


def test_mean_age_solves_the_first_moment_balance(baseline: dict) -> None:
    """reported residence times match independently solved age moments."""
    reference = baseline["reference"]
    reported = reported_fit(DATABASE)
    effects = dict(rows(DATABASE, "SELECT plot, input_scale FROM plot_fit"))
    ages = dict(rows(DATABASE, "SELECT plot || ':' || depth, mean_age FROM profile"))
    for name, plot in reference["problem"].items():
        expected = forward_plot(plot, reported["estimate"], float(effects[name]))[3]
        for index, depth in enumerate(plot["layers"][:, 0]):
            key = f"{name}:{float(depth)}"
            assert float(ages[key]) == pytest.approx(
                float(expected[index]), rel=5e-4, abs=1e-7,
            )


def test_interval_endpoints_reach_the_stated_criterion_rise(baseline: dict) -> None:
    """each endpoint reoptimizes the other parameters to the required rise."""
    reference = baseline["reference"]
    reported = reported_fit(DATABASE)
    endpoints = {
        name: (float(lower), float(upper))
        for name, lower, upper in rows(
            DATABASE, "SELECT parameter, lower, upper FROM fit_limits",
        )
    }
    assert set(endpoints) == set(PARAMETERS)
    target = reference["objective"] + THRESHOLD
    for index, name in enumerate(PARAMETERS):
        assert np.allclose(
            endpoints[name], reference["limits"][name], rtol=0.005, atol=2e-7,
        )
        for value in endpoints[name]:
            reached = profile_minimum(
                reference["problem"],
                reference["bounds"],
                reported["penalty"],
                reference["estimate"],
                index,
                value,
            )
            assert reached == pytest.approx(target, abs=0.02)


def test_changed_and_reordered_database_is_refit_without_hardcoding(
    baseline: dict, tmp_path: pathlib.Path,
) -> None:
    """a perturbed database with reversed insertion order earns a fresh fit."""
    altered = tmp_path / "altered.sqlite"
    shutil.copy2(DATABASE, altered)
    with sqlite3.connect(altered) as connection:
        connection.execute(
            "UPDATE forcing SET moisture_scale = moisture_scale * 0.83 "
            "WHERE plot IN ('alder', 'pine')",
        )
        for table in ("layers", "forcing", "observations"):
            connection.execute(
                f"UPDATE {table} SET plot = 'tundra' WHERE plot = 'spruce'",
            )
        for table in ("layers", "observations"):
            connection.execute(
                f"CREATE TABLE shuffled AS SELECT * FROM {table} "
                "ORDER BY plot DESC, depth DESC",
            )
            connection.execute(f"DELETE FROM {table}")
            connection.execute(f"INSERT INTO {table} SELECT * FROM shuffled")
            connection.execute("DROP TABLE shuffled")
    completed = run_command(altered)
    assert completed.returncode == 0, completed.stderr
    reference = reference_fit(altered, limits=False)
    reported = reported_fit(altered)
    assert reported["penalty"] == pytest.approx(reference["weight"], rel=1e-9)
    assert np.allclose(
        reported["estimate"], reference["estimate"], rtol=0.005, atol=2e-7,
    )
    assert reported["objective"] == pytest.approx(
        reference["objective"], rel=0.005, abs=0.02,
    )
    assert not np.allclose(
        reported["estimate"], baseline["reference"]["estimate"], rtol=1e-4,
    )


def test_candidate_set_drives_the_selection(
    baseline: dict, tmp_path: pathlib.Path,
) -> None:
    """withdrawing the winning candidate moves the penalty and the whole fit."""
    reference = baseline["reference"]
    reduced = tmp_path / "reduced.sqlite"
    shutil.copy2(DATABASE, reduced)
    with sqlite3.connect(reduced) as connection:
        connection.execute(
            "DELETE FROM penalty_grid WHERE ABS(weight - ?) < 1e-9",
            (reference["weight"],),
        )
    completed = run_command(reduced)
    assert completed.returncode == 0, completed.stderr
    remaining = {
        weight: scores
        for weight, scores in reference["curve"].items()
        if weight != reference["weight"]
    }
    expected = choose_weight(remaining)
    reported = reported_fit(reduced)
    assert reported["penalty"] == pytest.approx(expected, rel=1e-9)
    assert np.allclose(
        reported["estimate"], remaining[expected]["estimate"], rtol=0.005, atol=2e-7,
    )
    assert reported["objective"] == pytest.approx(
        remaining[expected]["train"], rel=0.005, abs=0.02,
    )
    assert rows(reduced, "SELECT COUNT(*) FROM cv_scores")[0][0] == 4


def test_input_tables_remain_unchanged(baseline: dict) -> None:
    """a successful fit replaces results without modifying any input row."""
    assert snapshot_inputs(DATABASE) == baseline["inputs"]


def test_invalid_inputs_fail_without_touching_results(
    baseline: dict, tmp_path: pathlib.Path,
) -> None:
    """rejected databases keep whatever result tables they already carried."""
    del baseline
    mutations = (
        "DROP TABLE forcing",
        "DELETE FROM observations WHERE plot = 'alder' AND depth = 5",
        "UPDATE observations SET sigma_f = 0 WHERE plot = 'birch' AND depth = 20",
        "UPDATE layers SET moisture = 0 WHERE plot = 'cedar'",
        "DELETE FROM penalty_grid",
        "UPDATE penalty_grid SET weight = -4 WHERE weight = 64.0",
        "UPDATE observations SET fold = 1",
    )
    for index, mutation in enumerate(mutations):
        invalid = tmp_path / f"invalid_{index}.sqlite"
        shutil.copy2(DATABASE, invalid)
        before = snapshot_outputs(invalid)
        with sqlite3.connect(invalid) as connection:
            connection.execute(mutation)
        completed = run_command(invalid)
        assert completed.returncode != 0
        assert snapshot_outputs(invalid) == before


def test_missing_database_returns_nonzero(tmp_path: pathlib.Path) -> None:
    """a nonexistent database path is rejected without creating a file."""
    missing = tmp_path / "missing.sqlite"
    completed = run_command(missing)
    assert completed.returncode != 0
    assert not missing.exists()
