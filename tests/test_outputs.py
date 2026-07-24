"""Deterministic artifact and held-out checks for a generated R MLE task."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "/app/config"))
OUT = Path(os.environ.get("OUT_DIR", os.environ.get("OUTPUT_DIR", "/app/outputs")))
LABELS = Path(os.environ.get("EVAL_LABELS_PATH", "/tests/eval/test_labels.csv"))
ANALYSIS = Path(os.environ.get("ANALYSIS_PATH", "/app/analysis.R"))


def read_key_values(path):
    frame = pd.read_csv(path)
    return dict(zip(frame["key"], frame["value"]))


def class_probability_columns(classes):
    return ["prob_" + "".join(ch.lower() if ch.isalnum() else "_" for ch in c).strip("_") for c in classes]


def macro_f1(actual, predicted, classes):
    return f1_score(actual, predicted, labels=classes, average="macro", zero_division=0)


MISSING_TOKENS = {"", "NA", "NaN", "nan", "null", "?", "MISSING"}


def is_missing(value):
    if pd.isna(value):
        return True
    return str(value).strip() in MISSING_TOKENS


def clean_numeric(series):
    values = pd.to_numeric(series, errors="coerce").astype(float)
    values[~np.isfinite(values)] = np.nan
    return values


def feature_rows(roles):
    return roles.loc[roles["role"] == "feature"].reset_index(drop=True)


def learn_encoder(frame, roles):
    encoders = {}
    for _, role in feature_rows(roles).iterrows():
        feature = role["feature"]
        if role["data_type"] == "numeric":
            values = clean_numeric(frame[feature])
            finite = values.dropna()
            med = float(finite.median()) if len(finite) else 0.0
            imputed = values.fillna(med).astype(float)
            center = float(imputed.mean())
            scale = float(imputed.std(ddof=1)) if len(imputed) > 1 else 1.0
            if not np.isfinite(scale) or scale < 1e-9:
                scale = 1.0
            encoders[feature] = {"type": "numeric", "median": med, "mean": center, "sd": scale}
        else:
            vals = ["__missing__" if is_missing(value) else str(value).strip() for value in frame[feature]]
            levels = sorted(set(vals))
            for extra in ["__missing__", "__other__"]:
                if extra not in levels:
                    levels.append(extra)
            encoders[feature] = {"type": "categorical", "levels": levels}
    return encoders


def apply_encoder(frame, encoders):
    parts = []
    for feature, encoder in encoders.items():
        if encoder["type"] == "numeric":
            values = clean_numeric(frame[feature]).fillna(encoder["median"]).astype(float)
            parts.append(((values - encoder["mean"]) / encoder["sd"]).to_numpy().reshape(-1, 1))
        else:
            vals = ["__missing__" if is_missing(value) else str(value).strip() for value in frame[feature]]
            vals = [value if value in encoder["levels"] else "__other__" for value in vals]
            mat = np.zeros((len(frame), len(encoder["levels"])), dtype=float)
            for idx, level in enumerate(encoder["levels"]):
                mat[:, idx] = [1.0 if value == level else 0.0 for value in vals]
            parts.append(mat)
    return np.column_stack(parts) if parts else np.zeros((len(frame), 0), dtype=float)


def fit_ridge(x, y, lambda_value):
    design = np.column_stack([np.ones(len(x)), x])
    penalty = np.eye(design.shape[1])
    penalty[0, 0] = 0.0
    return np.linalg.solve(design.T @ design + float(lambda_value) * penalty, design.T @ y)


def predict_ridge(beta, x):
    design = np.column_stack([np.ones(len(x)), x])
    return design @ beta


def target_for_model(y, use_log):
    return np.log1p(np.maximum(y, 0.0)) if use_log else y


def target_from_model(y, use_log):
    return np.maximum(0.0, np.expm1(y)) if use_log else y


def expected_selection_report(public_data, config, roles):
    """Recompute validation k selection with group-stability ranking."""
    split_col = config["split_column"]
    target_col = config["target_column"]
    group_col = config["group_column"]
    fit = public_data[public_data[split_col] == "fit"].reset_index(drop=True)
    validation = public_data[public_data[split_col] == "validation"].reset_index(drop=True)
    encoders = learn_encoder(fit, roles)
    fit_x = apply_encoder(fit, encoders)
    validation_x = apply_encoder(validation, encoders)
    fit_y = clean_numeric(fit[target_col]).to_numpy(float)
    validation_y = clean_numeric(validation[target_col]).to_numpy(float)
    use_log = bool(np.nanmin(np.concatenate([fit_y, validation_y])) >= 0.0)
    groups = validation[group_col].fillna("__missing__").astype(str).replace({"": "__missing__"})
    rows = []
    for candidate_k in [int(value) for value in str(config["k_grid"]).split("|")]:
        beta = fit_ridge(fit_x, target_for_model(fit_y, use_log), candidate_k)
        prediction = target_from_model(predict_ridge(beta, validation_x), use_log)
        rmse = float(np.sqrt(mean_squared_error(validation_y, prediction)))
        group_rmse = []
        for group in sorted(groups.unique()):
            mask = (groups == group).to_numpy()
            group_rmse.append(float(np.sqrt(mean_squared_error(validation_y[mask], prediction[mask]))))
        rows.append(
            {
                "candidate_k": candidate_k,
                "validation_metric": rmse,
                "worst_group_rmse": max(group_rmse),
                "best_group_rmse": min(group_rmse),
                "stability_gap": max(group_rmse) - min(group_rmse),
                "selected": False,
            }
        )
    selected_idx = min(
        range(len(rows)),
        key=lambda idx: (
            rows[idx]["stability_gap"],
            rows[idx]["validation_metric"],
            rows[idx]["candidate_k"],
        ),
    )
    rows[selected_idx]["selected"] = True
    return pd.DataFrame(rows)


def run_analysis(data_dir, out_dir):
    env = os.environ.copy()
    env["DATA_DIR"] = str(data_dir)
    env["DATA_PATH"] = str(data_dir / "train.csv")
    env["OUT_DIR"] = str(out_dir)
    env["OUTPUT_DIR"] = str(out_dir)
    result = subprocess.run(
        ["Rscript", str(ANALYSIS)],
        text=True,
        capture_output=True,
        timeout=420,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return out_dir


@pytest.fixture(scope="module")
def config():
    return read_key_values(CONFIG_DIR / "model_config.csv")


@pytest.fixture(scope="module")
def thresholds():
    return read_key_values(CONFIG_DIR / "evaluation_thresholds.csv")


@pytest.fixture(scope="module")
def roles():
    return pd.read_csv(CONFIG_DIR / "feature_roles.csv")


@pytest.fixture(scope="module")
def public_data():
    return pd.read_csv(DATA_DIR / "train.csv")


@pytest.fixture(scope="module")
def labels():
    return pd.read_csv(LABELS)


@pytest.fixture(scope="module")
def predictions():
    return pd.read_csv(OUT / "predictions.csv")


@pytest.fixture(scope="module")
def validation_predictions():
    return pd.read_csv(OUT / "validation_predictions.csv")


@pytest.fixture(scope="module")
def metrics():
    return json.loads((OUT / "metrics.json").read_text())


class TestPublicSurface:
    def test_required_artifacts_exist(self):
        """The required output files are present after the R analysis runs."""
        required = [
            "predictions.csv",
            "validation_predictions.csv",
            "metrics.json",
            "selection_report.csv",
            "feature_summary.csv",
            "group_error_report.csv",
            "neighbor_evidence.csv",
            "interval_report.csv",
            "residual_bins.csv",
        ]
        missing = [name for name in required if not (OUT / name).exists()]
        assert not missing

    def test_public_test_targets_are_blank(self, public_data, config):
        """The public data does not reveal target values for held-out test rows."""
        test_rows = public_data[public_data[config["split_column"]] == "test"]
        assert test_rows[config["target_column"]].isna().all()

    def test_feature_summary_matches_configured_features(self, roles):
        """feature_summary.csv covers exactly the configured feature set."""
        summary = pd.read_csv(OUT / "feature_summary.csv")
        expected = set(roles.loc[roles["role"] == "feature", "feature"])
        assert set(summary["feature"]) == expected


class TestPredictionContract:
    def test_predictions_cover_heldout_rows(self, predictions, labels):
        """predictions.csv covers every held-out row_id exactly once."""
        assert predictions["row_id"].is_unique
        assert set(predictions["row_id"]) == set(labels["row_id"])

    def test_predictions_are_sorted(self, predictions):
        """predictions.csv is sorted by row_id for deterministic upload checks."""
        values = predictions["row_id"].to_numpy()
        assert np.all(values[:-1] <= values[1:])

    def test_prediction_columns_match_task_mode(self, predictions, config):
        """The prediction schema matches the declared modeling mode."""
        if config["task_mode"] == "regression":
            assert {"prediction", "lower", "upper", "group_key"}.issubset(predictions)
            assert np.isfinite(predictions["prediction"]).all()
            assert (predictions["lower"] <= predictions["upper"]).all()
        else:
            classes = config["class_order"].split("|")
            prob_cols = class_probability_columns(classes)
            assert {"pred_label", "group_key"}.issubset(predictions)
            assert set(prob_cols).issubset(predictions)
            sums = predictions[prob_cols].sum(axis=1).to_numpy()
            np.testing.assert_allclose(sums, np.ones(len(sums)), atol=1e-4)


class TestValidationEvidence:
    def test_selection_report_has_one_selected_k(self, public_data, config, roles, metrics):
        """selection_report.csv recomputes validation group stability and marks the chosen k."""
        report = pd.read_csv(OUT / "selection_report.csv")
        assert list(report.columns) == [
            "candidate_k",
            "validation_metric",
            "worst_group_rmse",
            "best_group_rmse",
            "stability_gap",
            "selected",
        ]
        expected = expected_selection_report(public_data, config, roles)
        for column in [
            "candidate_k",
            "validation_metric",
            "worst_group_rmse",
            "best_group_rmse",
            "stability_gap",
        ]:
            np.testing.assert_allclose(report[column].astype(float), expected[column].astype(float), atol=5e-5)
        selected = report[report["selected"].astype(str).str.lower().isin(["true", "1"])]
        assert len(selected) == 1
        assert int(selected["candidate_k"].iloc[0]) == int(metrics["selected_k"])
        expected_selected = expected[expected["selected"]]
        assert int(selected["candidate_k"].iloc[0]) == int(expected_selected["candidate_k"].iloc[0])

    def test_group_report_uses_validation_groups(self, public_data, config):
        """group_error_report.csv reports only groups present in validation rows."""
        report = pd.read_csv(OUT / "group_error_report.csv")
        validation = public_data[public_data[config["split_column"]] == "validation"]
        assert set(report["group_key"]).issubset(set(validation[config["group_column"]]))
        assert (report["n_validation"] > 0).all()

    def test_metrics_match_validation_predictions(self, validation_predictions, metrics, config):
        """metrics.json is an honest summary of validation_predictions.csv."""
        if config["task_mode"] == "regression":
            rmse = np.sqrt(
                mean_squared_error(
                    validation_predictions["actual"],
                    validation_predictions["prediction"],
                )
            )
            mae = mean_absolute_error(
                validation_predictions["actual"],
                validation_predictions["prediction"],
            )
            assert abs(float(metrics["validation_rmse"]) - rmse) <= 1e-5
            assert abs(float(metrics["validation_mae"]) - mae) <= 1e-5
        else:
            classes = config["class_order"].split("|")
            acc = accuracy_score(
                validation_predictions["actual"].astype(str),
                validation_predictions["pred_label"].astype(str),
            )
            f1 = macro_f1(
                validation_predictions["actual"].astype(str),
                validation_predictions["pred_label"].astype(str),
                classes,
            )
            assert abs(float(metrics["validation_accuracy"]) - acc) <= 1e-5
            assert abs(float(metrics["validation_macro_f1"]) - f1) <= 1e-5

    def test_interval_and_residual_reports_are_contentful(self, validation_predictions, metrics, config):
        """Regression interval and residual-bin reports summarize validation predictions."""
        if config["task_mode"] != "regression":
            return
        interval = pd.read_csv(OUT / "interval_report.csv")
        assert list(interval.columns) == ["split", "interval_coverage", "mean_width"]
        assert len(interval) == 1
        assert interval["split"].iloc[0] == "validation"
        coverage = float(interval["interval_coverage"].iloc[0])
        assert 0.0 <= coverage <= 1.0
        assert abs(coverage - float(metrics["interval_coverage"])) <= 1e-5
        assert np.isfinite(float(interval["mean_width"].iloc[0]))
        assert float(interval["mean_width"].iloc[0]) >= 0.0

        residual_bins = pd.read_csv(OUT / "residual_bins.csv")
        assert list(residual_bins.columns) == ["prediction_bin", "mean_abs_error", "count"]
        assert not residual_bins.empty
        assert int(residual_bins["count"].sum()) == len(validation_predictions)
        assert (residual_bins["count"] > 0).all()


class TestHeldoutQuality:
    def test_heldout_score_clears_threshold(self, predictions, labels, config, thresholds):
        """Held-out labels score above the task-specific minimum quality bar."""
        merged = predictions.merge(labels, on="row_id", how="inner", validate="one_to_one")
        target = config["target_column"]
        if config["task_mode"] == "regression":
            rmse = np.sqrt(mean_squared_error(merged[target], merged["prediction"]))
            mae = mean_absolute_error(merged[target], merged["prediction"])
            r2 = r2_score(merged[target], merged["prediction"])
            assert rmse <= float(thresholds["max_rmse"])
            assert mae <= float(thresholds["max_mae"])
            assert r2 >= float(thresholds["min_r2"])
        else:
            classes = config["class_order"].split("|")
            acc = accuracy_score(merged[target].astype(str), merged["pred_label"].astype(str))
            f1 = macro_f1(
                merged[target].astype(str),
                merged["pred_label"].astype(str),
                classes,
            )
            assert acc >= float(thresholds["min_accuracy"])
            assert f1 >= float(thresholds["min_macro_f1"])

    def test_fit_label_perturbation_changes_predictions(self, tmp_path, predictions, config):
        """Changing fit labels changes held-out predictions in an alternate run."""
        alt_data = tmp_path / "data"
        shutil.copytree(DATA_DIR, alt_data)
        frame = pd.read_csv(alt_data / "train.csv")
        target = config["target_column"]
        fit_mask = frame[config["split_column"]] == "fit"
        if config["task_mode"] == "regression":
            values = pd.to_numeric(frame.loc[fit_mask, target])
            frame.loc[fit_mask, target] = values + values.std(ddof=0) * 0.75
        else:
            classes = config["class_order"].split("|")
            mapping = {classes[i]: classes[(i + 1) % len(classes)] for i in range(len(classes))}
            frame.loc[fit_mask, target] = frame.loc[fit_mask, target].astype(str).map(mapping)
        frame.to_csv(alt_data / "train.csv", index=False)
        alt_out = tmp_path / "out"
        alt_out.mkdir()
        run_analysis(alt_data, alt_out)
        changed = pd.read_csv(alt_out / "predictions.csv")
        merged = predictions.merge(changed, on="row_id", suffixes=("_orig", "_alt"))
        if config["task_mode"] == "regression":
            delta = np.abs(merged["prediction_orig"] - merged["prediction_alt"]).mean()
        else:
            classes = config["class_order"].split("|")
            prob_cols = class_probability_columns(classes)
            delta = 0.0
            for col in prob_cols:
                delta += np.abs(merged[f"{col}_orig"] - merged[f"{col}_alt"]).mean()
        assert delta > 1e-6
