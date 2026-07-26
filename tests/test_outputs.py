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


def cfg_int(config, key, default):
    value = str(config.get(key, default)).strip()
    return int(value) if value else int(default)


def write_config_with_updates(src_dir, dst_dir, updates):
    shutil.copytree(src_dir, dst_dir)
    frame = pd.read_csv(dst_dir / "model_config.csv")
    for key, value in updates.items():
        mask = frame["key"] == key
        if mask.any():
            frame.loc[mask, "value"] = str(value)
        else:
            frame = pd.concat([frame, pd.DataFrame([{"key": key, "value": str(value)}])], ignore_index=True)
    frame.to_csv(dst_dir / "model_config.csv", index=False)


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


def selected_lambda(public_data, config, roles):
    expected = expected_selection_report(public_data, config, roles)
    selected = expected[expected["selected"]]
    assert len(selected) == 1
    return int(selected["candidate_k"].iloc[0])


def expected_ridge_predictions(public_data, config, roles, split_name):
    """Recompute row-level ridge predictions for validation or test rows."""
    split_col = config["split_column"]
    target_col = config["target_column"]
    lambda_value = selected_lambda(public_data, config, roles)
    if split_name == "validation":
        train = public_data[public_data[split_col] == "fit"].reset_index(drop=True)
        evaluation = public_data[public_data[split_col] == "validation"].reset_index(drop=True)
        log_source = public_data[public_data[split_col].isin(["fit", "validation"])][target_col]
    elif split_name == "test":
        train = public_data[public_data[split_col].isin(["fit", "validation"])].reset_index(drop=True)
        evaluation = public_data[public_data[split_col] == "test"].reset_index(drop=True)
        log_source = train[target_col]
    else:
        raise ValueError(f"Unsupported split_name: {split_name}")
    encoders = learn_encoder(train, roles)
    train_x = apply_encoder(train, encoders)
    evaluation_x = apply_encoder(evaluation, encoders)
    train_y = clean_numeric(train[target_col]).to_numpy(float)
    log_values = clean_numeric(log_source).dropna().to_numpy(float)
    use_log = bool(len(log_values) and np.nanmin(log_values) >= 0.0)
    beta = fit_ridge(train_x, target_for_model(train_y, use_log), lambda_value)
    prediction = target_from_model(predict_ridge(beta, evaluation_x), use_log)
    return pd.DataFrame({"row_id": evaluation["row_id"], "expected_prediction": prediction}).sort_values("row_id")


def validation_interval_report(public_data, config, roles, selected_k):
    """Recompute validation interval coverage and width from fit-row neighbors."""
    split_col = config["split_column"]
    target_col = config["target_column"]
    fit = public_data[public_data[split_col] == "fit"].reset_index(drop=True)
    validation = public_data[public_data[split_col] == "validation"].reset_index(drop=True)
    encoders = learn_encoder(fit, roles)
    fit_x = apply_encoder(fit, encoders)
    validation_x = apply_encoder(validation, encoders)
    fit_y = clean_numeric(fit[target_col]).to_numpy(float)
    validation_y = clean_numeric(validation[target_col]).to_numpy(float)
    positions = np.arange(len(fit_x))
    k = min(int(selected_k), len(fit_x))
    lower = []
    upper = []
    for idx in range(len(validation_x)):
        distances = np.sqrt(((fit_x - validation_x[idx, :]) ** 2).sum(axis=1))
        nearest = np.lexsort((positions, distances))[:k]
        lower.append(float(np.quantile(fit_y[nearest], 0.08, method="median_unbiased")))
        upper.append(float(np.quantile(fit_y[nearest], 0.92, method="median_unbiased")))
    lower = np.asarray(lower)
    upper = np.asarray(upper)
    return pd.DataFrame(
        {
            "split": ["validation"],
            "interval_coverage": [round(float(np.mean((validation_y >= lower) & (validation_y <= upper))), 6)],
            "mean_width": [round(float(np.mean(upper - lower)), 6)],
        }
    )


def expected_residual_bins(validation_predictions):
    """Recompute prediction-quantile residual bins from serialized validation rows."""
    values = validation_predictions["prediction"].astype(float).to_numpy()
    errors = validation_predictions["abs_error"].astype(float).to_numpy()
    cuts = np.quantile(values, np.linspace(0, 1, 6), method="median_unbiased")
    cuts = np.unique(cuts)
    if len(cuts) < 2:
        cuts = np.array([values.min(), values.max() + 1e-6])
    rows = []
    for idx in range(len(cuts) - 1):
        lower = cuts[idx]
        upper = cuts[idx + 1]
        if idx == 0:
            mask = (values >= lower) & (values <= upper)
        else:
            mask = (values > lower) & (values <= upper)
        if np.any(mask):
            rows.append({"mean_abs_error": float(errors[mask].mean()), "count": int(mask.sum())})
    return pd.DataFrame(rows)


def expected_feature_pair_stress(public_data, config, roles):
    """Recompute final test prediction shifts from paired feature replacement."""
    split_col = config["split_column"]
    target_col = config["target_column"]
    train = public_data[public_data[split_col].isin(["fit", "validation"])].reset_index(drop=True)
    evaluation = public_data[public_data[split_col] == "test"].sort_values("row_id").reset_index(drop=True)
    encoders = learn_encoder(train, roles)
    train_x = apply_encoder(train, encoders)
    train_y = clean_numeric(train[target_col]).to_numpy(float)
    log_values = clean_numeric(train[target_col]).dropna().to_numpy(float)
    use_log = bool(len(log_values) and np.nanmin(log_values) >= 0.0)
    beta = fit_ridge(train_x, target_for_model(train_y, use_log), selected_lambda(public_data, config, roles))
    baseline_x = apply_encoder(evaluation, encoders)
    baseline = target_from_model(predict_ridge(beta, baseline_x), use_log)
    rows = []
    selected_features = feature_rows(roles).head(cfg_int(config, "feature_pair_stress_feature_count", 5)).reset_index(drop=True)
    for i, role_a in selected_features.iterrows():
        for _, role_b in selected_features.iloc[i + 1 :].iterrows():
            feature_a = role_a["feature"]
            feature_b = role_b["feature"]
            stressed = evaluation.copy()
            for role in [role_a, role_b]:
                feature = role["feature"]
                if role["data_type"] == "numeric":
                    stressed[feature] = encoders[feature]["median"]
                else:
                    stressed[feature] = encoders[feature]["levels"][0]
            stressed_x = apply_encoder(stressed, encoders)
            prediction = target_from_model(predict_ridge(beta, stressed_x), use_log)
            shift = prediction - baseline
            rows.append(
                {
                    "feature_a": feature_a,
                    "feature_b": feature_b,
                    "baseline_mean_prediction": float(np.mean(baseline)),
                    "stressed_mean_prediction": float(np.mean(prediction)),
                    "mean_prediction_shift": float(np.mean(shift)),
                    "mean_abs_prediction_shift": float(np.mean(np.abs(shift))),
                    "max_abs_prediction_shift": float(np.max(np.abs(shift))),
                }
            )
    rows.sort(
        key=lambda row: (
            -row["mean_abs_prediction_shift"],
            -row["max_abs_prediction_shift"],
            row["feature_a"],
            row["feature_b"],
        )
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return pd.DataFrame(
        rows,
        columns=[
            "rank",
            "feature_a",
            "feature_b",
            "baseline_mean_prediction",
            "stressed_mean_prediction",
            "mean_prediction_shift",
            "mean_abs_prediction_shift",
            "max_abs_prediction_shift",
        ],
    )


def expected_feature_summary(public_data, config, roles):
    """Recompute feature missingness counts by split."""
    rows = []
    split_col = config["split_column"]
    for _, role in feature_rows(roles).iterrows():
        feature = role["feature"]
        row = {"feature": feature, "data_type": role["data_type"]}
        for split_name, column in [
            ("fit", "missing_fit"),
            ("validation", "missing_validation"),
            ("test", "missing_test"),
        ]:
            values = public_data.loc[public_data[split_col] == split_name, feature]
            row[column] = int(sum(is_missing(value) for value in values))
        rows.append(row)
    return pd.DataFrame(rows)


def expected_group_error_report(validation_predictions):
    """Recompute validation group mean absolute errors."""
    source = validation_predictions.copy()
    groups = source["group_key"].apply(lambda value: "__missing__" if is_missing(value) else str(value).strip())
    source["group_key"] = groups
    return (
        source.groupby("group_key", sort=True)
        .agg(mean_abs_error=("abs_error", "mean"), n_validation=("abs_error", "size"))
        .reset_index()
    )


def expected_neighbor_evidence(public_data, config, roles):
    """Recompute nearest final-reference row for the neighbor evidence report."""
    split_col = config["split_column"]
    lambda_value = selected_lambda(public_data, config, roles)
    _ = lambda_value  # The selected k/lambda fixes the final model; nearest row uses the same final encoding.
    train = public_data[public_data[split_col].isin(["fit", "validation"])].reset_index(drop=True)
    evaluation = (
        public_data[public_data[split_col] == "test"]
        .sort_values("row_id")
        .reset_index(drop=True)
    )
    encoders = learn_encoder(train, roles)
    train_x = apply_encoder(train, encoders)
    evaluation_x = apply_encoder(evaluation, encoders)
    rows = []
    for idx in range(min(50, len(evaluation))):
        distances = np.sqrt(((train_x - evaluation_x[idx, :]) ** 2).sum(axis=1))
        nearest = int(np.argsort(distances, kind="mergesort")[0])
        rows.append(
            {
                "row_id": evaluation["row_id"].iloc[idx],
                "nearest_fit_index": nearest + 1,
                "nearest_distance": round(float(distances[nearest]), 6),
            }
        )
    return pd.DataFrame(rows)


def run_analysis(data_dir, out_dir, config_dir=None):
    env = os.environ.copy()
    config_dir = CONFIG_DIR if config_dir is None else Path(config_dir)
    env["DATA_DIR"] = str(data_dir)
    env["DATA_PATH"] = str(data_dir / "train.csv")
    env["CONFIG_DIR"] = str(config_dir)
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
            "feature_pair_stress_report.csv",
        ]
        missing = [name for name in required if not (OUT / name).exists()]
        assert not missing

    def test_public_test_targets_are_blank(self, public_data, config):
        """The public data does not reveal target values for held-out test rows."""
        test_rows = public_data[public_data[config["split_column"]] == "test"]
        assert test_rows[config["target_column"]].isna().all()

    def test_feature_summary_matches_configured_features(self, public_data, config, roles):
        """feature_summary.csv covers features and split-specific missing counts."""
        summary = pd.read_csv(OUT / "feature_summary.csv")
        assert list(summary.columns) == [
            "feature",
            "data_type",
            "missing_fit",
            "missing_validation",
            "missing_test",
        ]
        expected = expected_feature_summary(public_data, config, roles)
        summary = summary.sort_values("feature").reset_index(drop=True)
        expected = expected.sort_values("feature").reset_index(drop=True)
        pd.testing.assert_frame_equal(summary, expected, check_dtype=False)


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

    def test_group_report_uses_validation_groups(self, validation_predictions):
        """group_error_report.csv recomputes validation group mean errors."""
        report = pd.read_csv(OUT / "group_error_report.csv")
        assert list(report.columns) == ["group_key", "mean_abs_error", "n_validation"]
        assert report["group_key"].is_unique
        assert (report["n_validation"] > 0).all()
        expected = expected_group_error_report(validation_predictions)
        report = report.sort_values("group_key").reset_index(drop=True)
        expected = expected.sort_values("group_key").reset_index(drop=True)
        assert report["group_key"].tolist() == expected["group_key"].tolist()
        assert report["n_validation"].astype(int).tolist() == expected["n_validation"].astype(int).tolist()
        np.testing.assert_allclose(report["mean_abs_error"], expected["mean_abs_error"], atol=1e-6)

    def test_neighbor_evidence_matches_reference(self, public_data, config, roles):
        """neighbor_evidence.csv recomputes nearest final-reference rows."""
        report = pd.read_csv(OUT / "neighbor_evidence.csv")
        assert list(report.columns) == ["row_id", "nearest_fit_index", "nearest_distance"]
        expected = expected_neighbor_evidence(public_data, config, roles)
        assert len(report) == len(expected)
        assert report["row_id"].tolist() == expected["row_id"].tolist()
        assert report["nearest_fit_index"].astype(int).tolist() == expected["nearest_fit_index"].astype(int).tolist()
        assert (report["nearest_distance"] >= 0).all()
        np.testing.assert_allclose(report["nearest_distance"], expected["nearest_distance"], atol=5e-6)

    def test_metrics_match_validation_predictions(self, validation_predictions, metrics, config, public_data, roles):
        """metrics.json is an honest summary of the selected fit-only validation model."""
        if config["task_mode"] == "regression":
            expected = expected_ridge_predictions(public_data, config, roles, "validation")
            merged = validation_predictions.merge(expected, on="row_id", how="inner", validate="one_to_one")
            np.testing.assert_allclose(merged["prediction"], merged["expected_prediction"], atol=1e-4)
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

    def test_interval_and_residual_reports_are_contentful(self, public_data, roles, validation_predictions, metrics, config):
        """Regression interval and residual-bin reports summarize validation predictions."""
        if config["task_mode"] != "regression":
            return
        expected_interval = validation_interval_report(public_data, config, roles, metrics["selected_k"])
        interval = pd.read_csv(OUT / "interval_report.csv")
        assert list(interval.columns) == ["split", "interval_coverage", "mean_width"]
        assert len(interval) == 1
        assert interval["split"].iloc[0] == "validation"
        coverage = float(interval["interval_coverage"].iloc[0])
        assert 0.0 <= coverage <= 1.0
        assert abs(coverage - float(metrics["interval_coverage"])) <= 1e-5
        assert np.isfinite(float(interval["mean_width"].iloc[0]))
        assert float(interval["mean_width"].iloc[0]) >= 0.0
        np.testing.assert_allclose(
            interval[["interval_coverage", "mean_width"]].astype(float),
            expected_interval[["interval_coverage", "mean_width"]].astype(float),
            atol=5e-6,
        )

        residual_bins = pd.read_csv(OUT / "residual_bins.csv")
        assert list(residual_bins.columns) == ["prediction_bin", "mean_abs_error", "count"]
        assert not residual_bins.empty
        assert int(residual_bins["count"].sum()) == len(validation_predictions)
        assert (residual_bins["count"] > 0).all()
        expected_bins = expected_residual_bins(validation_predictions)
        assert len(residual_bins) == len(expected_bins)
        np.testing.assert_array_equal(residual_bins["count"].astype(int), expected_bins["count"].astype(int))
        np.testing.assert_allclose(
            residual_bins["mean_abs_error"].astype(float),
            expected_bins["mean_abs_error"].astype(float),
            atol=5e-6,
        )

    def test_feature_pair_stress_matches_reference(self, public_data, config, roles):
        """feature_pair_stress_report.csv recomputes paired test-feature sensitivity."""
        if config["task_mode"] != "regression":
            return
        report = pd.read_csv(OUT / "feature_pair_stress_report.csv")
        expected = expected_feature_pair_stress(public_data, config, roles)
        assert list(report.columns) == list(expected.columns)
        assert len(report) == len(expected)
        assert report[["rank", "feature_a", "feature_b"]].astype(str).values.tolist() == expected[
            ["rank", "feature_a", "feature_b"]
        ].astype(str).values.tolist()
        for column in [
            "baseline_mean_prediction",
            "stressed_mean_prediction",
            "mean_prediction_shift",
            "mean_abs_prediction_shift",
            "max_abs_prediction_shift",
        ]:
            np.testing.assert_allclose(report[column].astype(float), expected[column].astype(float), atol=5e-6)


class TestHeldoutQuality:
    def test_heldout_score_clears_threshold(self, predictions, labels, config, thresholds, public_data, roles):
        """Held-out predictions match the selected refit model and clear quality bars."""
        merged = predictions.merge(labels, on="row_id", how="inner", validate="one_to_one")
        target = config["target_column"]
        if config["task_mode"] == "regression":
            expected = expected_ridge_predictions(public_data, config, roles, "test")
            checked = predictions.merge(expected, on="row_id", how="inner", validate="one_to_one")
            np.testing.assert_allclose(checked["prediction"], checked["expected_prediction"], atol=1e-4)
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

    def test_feature_pair_stress_honors_configured_feature_count(self, tmp_path, public_data, roles):
        """Changing feature_pair_stress_feature_count changes the paired stress audit."""
        alt_data = tmp_path / "data"
        alt_config = tmp_path / "config"
        alt_out = tmp_path / "out"
        shutil.copytree(DATA_DIR, alt_data)
        write_config_with_updates(CONFIG_DIR, alt_config, {"feature_pair_stress_feature_count": 3})
        alt_out.mkdir()
        run_analysis(alt_data, alt_out, alt_config)

        mutated_config = read_key_values(alt_config / "model_config.csv")
        expected = expected_feature_pair_stress(public_data, mutated_config, roles)
        report = pd.read_csv(alt_out / "feature_pair_stress_report.csv")
        assert len(report) == len(expected) == 3
        assert report[["rank", "feature_a", "feature_b"]].astype(str).values.tolist() == expected[
            ["rank", "feature_a", "feature_b"]
        ].astype(str).values.tolist()
        for column in [
            "baseline_mean_prediction",
            "stressed_mean_prediction",
            "mean_prediction_shift",
            "mean_abs_prediction_shift",
            "max_abs_prediction_shift",
        ]:
            np.testing.assert_allclose(report[column].astype(float), expected[column].astype(float), atol=5e-6)
