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


def cfg_float(config, key, default):
    value = str(config.get(key, default)).strip()
    return float(value) if value else float(default)


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


def read_feature_policies(config_dir, config, roles):
    """Load ordered feature policies and preserve configured feature-role order."""
    frame = pd.read_csv(Path(config_dir) / config["feature_policy_file"]).sort_values("policy_order")
    configured = feature_rows(roles)["feature"].tolist()
    policies = []
    for row in frame.itertuples(index=False):
        requested = str(row.active_features).split("|")
        active = [feature for feature in configured if feature in requested]
        assert active and len(active) == len(set(requested)) and set(requested).issubset(configured)
        policies.append(
            {
                "policy": str(row.policy),
                "active_features": active,
                "policy_order": int(row.policy_order),
            }
        )
    return policies


def roles_for_policy(roles, active_features):
    """Keep selected features plus non-feature metadata rows."""
    return roles[(roles["role"] != "feature") | roles["feature"].isin(active_features)].copy()


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


def configured_feature_pairs(roles, pair_count):
    """Return the configured deterministic prefix of unordered feature pairs."""
    features = feature_rows(roles)["feature"].tolist()
    pairs = [
        (features[i], features[j])
        for i in range(len(features) - 1)
        for j in range(i + 1, len(features))
    ]
    return pairs[: max(0, min(int(pair_count), len(pairs)))]


def expected_robust_selection_report(public_data, config, roles, policies):
    """Independently recompute the joint feature-policy and lambda surface."""
    split_col = config["split_column"]
    target_col = config["target_column"]
    group_col = config["group_column"]
    fit = public_data[public_data[split_col] == "fit"].reset_index(drop=True)
    validation = public_data[public_data[split_col] == "validation"].reset_index(drop=True)
    fit_y = clean_numeric(fit[target_col]).to_numpy(float)
    validation_y = clean_numeric(validation[target_col]).to_numpy(float)
    use_log = bool(np.nanmin(np.concatenate([fit_y, validation_y])) >= 0.0)
    groups = validation[group_col].fillna("__missing__").astype(str).replace({"": "__missing__"})
    pair_count = cfg_int(config, "robust_selection_pair_count", 5)
    weight_rmse = cfg_float(config, "robust_weight_validation_rmse", 1.0)
    weight_gap = cfg_float(config, "robust_weight_stability_gap", 0.25)
    weight_shift = cfg_float(config, "robust_weight_pair_shift", 0.03)
    rows = []
    for policy in policies:
        policy_roles = roles_for_policy(roles, policy["active_features"])
        encoders = learn_encoder(fit, policy_roles)
        fit_x = apply_encoder(fit, encoders)
        validation_x = apply_encoder(validation, encoders)
        pairs = configured_feature_pairs(policy_roles, pair_count)
        for candidate_lambda in [float(value) for value in str(config["lambda_grid"]).split("|")]:
            beta = fit_ridge(fit_x, target_for_model(fit_y, use_log), candidate_lambda)
            prediction = target_from_model(predict_ridge(beta, validation_x), use_log)
            rmse = float(np.sqrt(mean_squared_error(validation_y, prediction)))
            group_rmse = []
            for group in sorted(groups.unique()):
                mask = (groups == group).to_numpy()
                group_rmse.append(float(np.sqrt(mean_squared_error(validation_y[mask], prediction[mask]))))
            pair_shifts = []
            for feature_a, feature_b in pairs:
                stressed = validation.copy()
                for feature in [feature_a, feature_b]:
                    state = encoders[feature]
                    stressed[feature] = state["median"] if state["type"] == "numeric" else state["levels"][0]
                stressed_prediction = target_from_model(
                    predict_ridge(beta, apply_encoder(stressed, encoders)),
                    use_log,
                )
                pair_shifts.append(float(np.mean(np.abs(stressed_prediction - prediction))))
            mean_pair_shift = float(np.mean(pair_shifts)) if pair_shifts else 0.0
            stability_gap = max(group_rmse) - min(group_rmse)
            robust_score = weight_rmse * rmse + weight_gap * stability_gap + weight_shift * mean_pair_shift
            rows.append(
                {
                    "candidate_policy": policy["policy"],
                    "candidate_lambda": candidate_lambda,
                    "active_feature_count": len(policy["active_features"]),
                    "validation_rmse": rmse,
                    "stability_gap": stability_gap,
                    "mean_abs_pair_shift": mean_pair_shift,
                    "robust_score": robust_score,
                    "policy_order": policy["policy_order"],
                }
            )
    expected = pd.DataFrame(rows).sort_values(
        ["robust_score", "validation_rmse", "policy_order", "candidate_lambda"],
        kind="mergesort",
    ).reset_index(drop=True)
    expected.insert(0, "rank", np.arange(1, len(expected) + 1))
    expected["selected"] = expected["rank"] == 1
    return expected.drop(columns=["policy_order"])


def selected_candidate(public_data, config, roles, policies):
    expected = expected_robust_selection_report(public_data, config, roles, policies)
    selected = expected[expected["selected"]]
    assert len(selected) == 1
    policy_name = str(selected["candidate_policy"].iloc[0])
    policy = next(item for item in policies if item["policy"] == policy_name)
    return policy, float(selected["candidate_lambda"].iloc[0])


def expected_ridge_predictions(public_data, config, roles, policies, split_name):
    """Recompute row-level ridge predictions for validation or test rows."""
    split_col = config["split_column"]
    target_col = config["target_column"]
    policy, lambda_value = selected_candidate(public_data, config, roles, policies)
    policy_roles = roles_for_policy(roles, policy["active_features"])
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
    encoders = learn_encoder(train, policy_roles)
    train_x = apply_encoder(train, encoders)
    evaluation_x = apply_encoder(evaluation, encoders)
    train_y = clean_numeric(train[target_col]).to_numpy(float)
    log_values = clean_numeric(log_source).dropna().to_numpy(float)
    use_log = bool(len(log_values) and np.nanmin(log_values) >= 0.0)
    beta = fit_ridge(train_x, target_for_model(train_y, use_log), lambda_value)
    prediction = target_from_model(predict_ridge(beta, evaluation_x), use_log)
    return pd.DataFrame({"row_id": evaluation["row_id"], "expected_prediction": prediction}).sort_values("row_id")


def validation_interval_report(public_data, config, roles, policies, selected_k):
    """Recompute validation interval coverage and width from fit-row neighbors."""
    split_col = config["split_column"]
    target_col = config["target_column"]
    fit = public_data[public_data[split_col] == "fit"].reset_index(drop=True)
    validation = public_data[public_data[split_col] == "validation"].reset_index(drop=True)
    policy, _ = selected_candidate(public_data, config, roles, policies)
    encoders = learn_encoder(fit, roles_for_policy(roles, policy["active_features"]))
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


def expected_test_intervals(public_data, config, roles, policies):
    """Recompute final test intervals from the selected robust lambda."""
    split_col = config["split_column"]
    target_col = config["target_column"]
    train = public_data[public_data[split_col].isin(["fit", "validation"])].reset_index(drop=True)
    evaluation = public_data[public_data[split_col] == "test"].sort_values("row_id").reset_index(drop=True)
    policy, lambda_value = selected_candidate(public_data, config, roles, policies)
    encoders = learn_encoder(train, roles_for_policy(roles, policy["active_features"]))
    train_x = apply_encoder(train, encoders)
    evaluation_x = apply_encoder(evaluation, encoders)
    train_y = clean_numeric(train[target_col]).to_numpy(float)
    positions = np.arange(len(train_x))
    neighbor_count = min(int(lambda_value), len(train_x))
    lower = []
    upper = []
    for idx in range(len(evaluation_x)):
        distances = np.sqrt(((train_x - evaluation_x[idx, :]) ** 2).sum(axis=1))
        nearest = np.lexsort((positions, distances))[:neighbor_count]
        lower.append(float(np.quantile(train_y[nearest], 0.08, method="median_unbiased")))
        upper.append(float(np.quantile(train_y[nearest], 0.92, method="median_unbiased")))
    return pd.DataFrame({"row_id": evaluation["row_id"], "lower": lower, "upper": upper})


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


def expected_feature_pair_stress(public_data, config, roles, policies):
    """Recompute final test prediction shifts from paired feature replacement."""
    split_col = config["split_column"]
    target_col = config["target_column"]
    train = public_data[public_data[split_col].isin(["fit", "validation"])].reset_index(drop=True)
    evaluation = public_data[public_data[split_col] == "test"].sort_values("row_id").reset_index(drop=True)
    policy, lambda_value = selected_candidate(public_data, config, roles, policies)
    policy_roles = roles_for_policy(roles, policy["active_features"])
    encoders = learn_encoder(train, policy_roles)
    train_x = apply_encoder(train, encoders)
    train_y = clean_numeric(train[target_col]).to_numpy(float)
    log_values = clean_numeric(train[target_col]).dropna().to_numpy(float)
    use_log = bool(len(log_values) and np.nanmin(log_values) >= 0.0)
    beta = fit_ridge(train_x, target_for_model(train_y, use_log), lambda_value)
    baseline_x = apply_encoder(evaluation, encoders)
    baseline = target_from_model(predict_ridge(beta, baseline_x), use_log)
    rows = []
    selected_features = feature_rows(policy_roles).head(
        cfg_int(config, "feature_pair_stress_feature_count", 5)
    ).reset_index(drop=True)
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


def expected_feature_summary(public_data, config, roles, policies):
    """Recompute feature missingness counts by split."""
    rows = []
    split_col = config["split_column"]
    policy, _ = selected_candidate(public_data, config, roles, policies)
    for _, role in feature_rows(roles).iterrows():
        feature = role["feature"]
        row = {
            "feature": feature,
            "data_type": role["data_type"],
            "active_in_policy": feature in policy["active_features"],
        }
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


def expected_neighbor_evidence(public_data, config, roles, policies):
    """Recompute nearest final-reference row for the neighbor evidence report."""
    split_col = config["split_column"]
    policy, lambda_value = selected_candidate(public_data, config, roles, policies)
    train = public_data[public_data[split_col].isin(["fit", "validation"])].reset_index(drop=True)
    evaluation = (
        public_data[public_data[split_col] == "test"]
        .sort_values("row_id")
        .reset_index(drop=True)
    )
    encoders = learn_encoder(train, roles_for_policy(roles, policy["active_features"]))
    train_x = apply_encoder(train, encoders)
    evaluation_x = apply_encoder(evaluation, encoders)
    rows = []
    for idx in range(min(50, len(evaluation))):
        distances = np.sqrt(((train_x - evaluation_x[idx, :]) ** 2).sum(axis=1))
        nearest = int(np.argsort(distances, kind="mergesort")[0])
        rows.append(
            {
                "row_id": evaluation["row_id"].iloc[idx],
                "selected_policy": policy["policy"],
                "selected_lambda": lambda_value,
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
def policies(config, roles):
    return read_feature_policies(CONFIG_DIR, config, roles)


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
            "model_manifest.json",
            "robust_selection_report.csv",
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

    def test_feature_summary_matches_configured_features(self, public_data, config, roles, policies):
        """feature_summary.csv covers features and split-specific missing counts."""
        summary = pd.read_csv(OUT / "feature_summary.csv")
        assert list(summary.columns) == [
            "feature",
            "data_type",
            "active_in_policy",
            "missing_fit",
            "missing_validation",
            "missing_test",
        ]
        expected = expected_feature_summary(public_data, config, roles, policies)
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
    def test_robust_selection_report_drives_joint_winner(self, public_data, config, roles, policies, metrics):
        """The robust report independently scores every policy-lambda candidate."""
        report = pd.read_csv(OUT / "robust_selection_report.csv")
        assert list(report.columns) == [
            "rank",
            "candidate_policy",
            "candidate_lambda",
            "active_feature_count",
            "validation_rmse",
            "stability_gap",
            "mean_abs_pair_shift",
            "robust_score",
            "selected",
        ]
        expected = expected_robust_selection_report(public_data, config, roles, policies)
        for column in [
            "rank",
            "candidate_lambda",
            "active_feature_count",
            "validation_rmse",
            "stability_gap",
            "mean_abs_pair_shift",
            "robust_score",
        ]:
            np.testing.assert_allclose(report[column].astype(float), expected[column].astype(float), atol=5e-5)
        assert report["candidate_policy"].tolist() == expected["candidate_policy"].tolist()
        selected = report[report["selected"].astype(str).str.lower().isin(["true", "1"])]
        assert len(selected) == 1
        assert str(selected["candidate_policy"].iloc[0]) == str(metrics["selected_policy"])
        assert float(selected["candidate_lambda"].iloc[0]) == float(metrics["selected_lambda"])
        expected_selected = expected[expected["selected"]]
        assert str(selected["candidate_policy"].iloc[0]) == str(expected_selected["candidate_policy"].iloc[0])
        assert float(selected["candidate_lambda"].iloc[0]) == float(expected_selected["candidate_lambda"].iloc[0])
        assert str(selected["candidate_policy"].iloc[0]) == "without_width"
        assert float(selected["candidate_lambda"].iloc[0]) == 11.0

    def test_manifest_records_joint_winner(self, config, roles, policies, metrics):
        """The manifest preserves configured and selected feature identities."""
        manifest = json.loads((OUT / "model_manifest.json").read_text())
        selected = next(policy for policy in policies if policy["policy"] == metrics["selected_policy"])
        configured_features = feature_rows(roles)["feature"].tolist()
        assert manifest == {
            "task_mode": config["task_mode"],
            "target_column": config["target_column"],
            "model_family": "scaled_mixed_ridge_knn_evidence",
            "selected_policy": metrics["selected_policy"],
            "selected_lambda": metrics["selected_lambda"],
            "feature_columns": configured_features,
            "active_feature_columns": selected["active_features"],
            "feature_policy_source": config["feature_policy_file"],
        }

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

    def test_neighbor_evidence_matches_reference(self, public_data, config, roles, policies):
        """neighbor_evidence.csv recomputes nearest final-reference rows."""
        report = pd.read_csv(OUT / "neighbor_evidence.csv")
        assert list(report.columns) == [
            "row_id",
            "selected_policy",
            "selected_lambda",
            "nearest_fit_index",
            "nearest_distance",
        ]
        expected = expected_neighbor_evidence(public_data, config, roles, policies)
        assert len(report) == len(expected)
        assert report["row_id"].tolist() == expected["row_id"].tolist()
        assert report["selected_policy"].tolist() == expected["selected_policy"].tolist()
        np.testing.assert_allclose(report["selected_lambda"], expected["selected_lambda"], atol=1e-12)
        assert report["nearest_fit_index"].astype(int).tolist() == expected["nearest_fit_index"].astype(int).tolist()
        assert (report["nearest_distance"] >= 0).all()
        np.testing.assert_allclose(report["nearest_distance"], expected["nearest_distance"], atol=5e-6)

    def test_metrics_match_validation_predictions(
        self, validation_predictions, metrics, config, public_data, roles, policies
    ):
        """metrics.json is an honest summary of the selected fit-only validation model."""
        if config["task_mode"] == "regression":
            expected = expected_ridge_predictions(public_data, config, roles, policies, "validation")
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

    def test_interval_and_residual_reports_are_contentful(
        self, public_data, roles, policies, validation_predictions, metrics, config
    ):
        """Regression interval and residual-bin reports summarize validation predictions."""
        if config["task_mode"] != "regression":
            return
        expected_interval = validation_interval_report(
            public_data, config, roles, policies, metrics["selected_lambda"]
        )
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

    def test_feature_pair_stress_matches_reference(self, public_data, config, roles, policies):
        """feature_pair_stress_report.csv recomputes paired test-feature sensitivity."""
        if config["task_mode"] != "regression":
            return
        report = pd.read_csv(OUT / "feature_pair_stress_report.csv")
        expected = expected_feature_pair_stress(public_data, config, roles, policies)
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
    def test_heldout_score_clears_threshold(
        self, predictions, labels, config, thresholds, public_data, roles, policies
    ):
        """Held-out predictions match the selected refit model and clear quality bars."""
        merged = predictions.merge(labels, on="row_id", how="inner", validate="one_to_one")
        target = config["target_column"]
        if config["task_mode"] == "regression":
            expected = expected_ridge_predictions(public_data, config, roles, policies, "test")
            checked = predictions.merge(expected, on="row_id", how="inner", validate="one_to_one")
            np.testing.assert_allclose(checked["prediction"], checked["expected_prediction"], atol=1e-4)
            expected_intervals = expected_test_intervals(public_data, config, roles, policies)
            checked_intervals = predictions.merge(
                expected_intervals,
                on="row_id",
                how="inner",
                validate="one_to_one",
                suffixes=("", "_expected"),
            )
            np.testing.assert_allclose(checked_intervals["lower"], checked_intervals["lower_expected"], atol=5e-6)
            np.testing.assert_allclose(checked_intervals["upper"], checked_intervals["upper_expected"], atol=5e-6)
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

    def test_feature_pair_stress_honors_configured_feature_count(
        self, tmp_path, public_data, roles
    ):
        """Changing feature_pair_stress_feature_count changes the paired stress audit."""
        alt_data = tmp_path / "data"
        alt_config = tmp_path / "config"
        alt_out = tmp_path / "out"
        shutil.copytree(DATA_DIR, alt_data)
        write_config_with_updates(CONFIG_DIR, alt_config, {"feature_pair_stress_feature_count": 3})
        alt_out.mkdir()
        run_analysis(alt_data, alt_out, alt_config)

        mutated_config = read_key_values(alt_config / "model_config.csv")
        mutated_policies = read_feature_policies(alt_config, mutated_config, roles)
        expected = expected_feature_pair_stress(public_data, mutated_config, roles, mutated_policies)
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

    def test_joint_selection_config_recomputes_downstream_outputs(
        self,
        tmp_path,
        public_data,
        roles,
        metrics,
        predictions,
    ):
        """Changed robust config selects a new lambda and propagates through every dependent artifact."""
        alt_data = tmp_path / "robust_data"
        alt_config = tmp_path / "robust_config"
        alt_out = tmp_path / "robust_out"
        shutil.copytree(DATA_DIR, alt_data)
        write_config_with_updates(
            CONFIG_DIR,
            alt_config,
            {
                "robust_selection_pair_count": 5,
                "robust_weight_validation_rmse": 1,
                "robust_weight_stability_gap": 0,
                "robust_weight_pair_shift": 0,
            },
        )
        alt_out.mkdir()
        run_analysis(alt_data, alt_out, alt_config)

        mutated_config = read_key_values(alt_config / "model_config.csv")
        mutated_policies = read_feature_policies(alt_config, mutated_config, roles)
        expected_selection = expected_robust_selection_report(
            public_data, mutated_config, roles, mutated_policies
        )
        report = pd.read_csv(alt_out / "robust_selection_report.csv")
        for column in [
            "rank",
            "candidate_lambda",
            "active_feature_count",
            "validation_rmse",
            "stability_gap",
            "mean_abs_pair_shift",
            "robust_score",
        ]:
            np.testing.assert_allclose(report[column].astype(float), expected_selection[column].astype(float), atol=5e-5)
        assert report["candidate_policy"].tolist() == expected_selection["candidate_policy"].tolist()
        expected_winner = float(expected_selection.loc[expected_selection["selected"], "candidate_lambda"].iloc[0])
        expected_policy = str(expected_selection.loc[expected_selection["selected"], "candidate_policy"].iloc[0])
        selected = report[report["selected"].astype(str).str.lower().isin(["true", "1"])]
        assert len(selected) == 1
        assert str(selected["candidate_policy"].iloc[0]) == expected_policy == "without_spine"
        assert float(selected["candidate_lambda"].iloc[0]) == expected_winner == 3.0
        assert (expected_policy, expected_winner) != (
            str(metrics["selected_policy"]),
            float(metrics["selected_lambda"]),
        )

        alt_metrics = json.loads((alt_out / "metrics.json").read_text())
        assert str(alt_metrics["selected_policy"]) == expected_policy
        assert float(alt_metrics["selected_lambda"]) == expected_winner

        alt_manifest = json.loads((alt_out / "model_manifest.json").read_text())
        assert alt_manifest["selected_policy"] == expected_policy
        assert float(alt_manifest["selected_lambda"]) == expected_winner
        expected_active = next(
            policy["active_features"] for policy in mutated_policies if policy["policy"] == expected_policy
        )
        assert alt_manifest["active_feature_columns"] == expected_active

        alt_validation = pd.read_csv(alt_out / "validation_predictions.csv")
        expected_validation = expected_ridge_predictions(
            public_data, mutated_config, roles, mutated_policies, "validation"
        )
        checked_validation = alt_validation.merge(expected_validation, on="row_id", validate="one_to_one")
        np.testing.assert_allclose(
            checked_validation["prediction"],
            checked_validation["expected_prediction"],
            atol=1e-4,
        )

        alt_predictions = pd.read_csv(alt_out / "predictions.csv")
        expected_predictions = expected_ridge_predictions(
            public_data, mutated_config, roles, mutated_policies, "test"
        )
        checked_predictions = alt_predictions.merge(expected_predictions, on="row_id", validate="one_to_one")
        np.testing.assert_allclose(
            checked_predictions["prediction"],
            checked_predictions["expected_prediction"],
            atol=1e-4,
        )
        changed = predictions.merge(alt_predictions, on="row_id", suffixes=("_public", "_mutated"))
        assert np.mean(np.abs(changed["prediction_public"] - changed["prediction_mutated"])) > 1e-4

        alt_summary = pd.read_csv(alt_out / "feature_summary.csv")
        active = alt_summary.loc[alt_summary["active_in_policy"].astype(str).str.lower() == "true", "feature"]
        assert active.tolist() == expected_active
        expected_intervals = expected_test_intervals(public_data, mutated_config, roles, mutated_policies)
        checked_intervals = alt_predictions.merge(
            expected_intervals,
            on="row_id",
            validate="one_to_one",
            suffixes=("", "_expected"),
        )
        np.testing.assert_allclose(checked_intervals["lower"], checked_intervals["lower_expected"], atol=5e-6)
        np.testing.assert_allclose(checked_intervals["upper"], checked_intervals["upper_expected"], atol=5e-6)

        expected_interval_report = validation_interval_report(
            public_data, mutated_config, roles, mutated_policies, expected_winner
        )
        interval_report = pd.read_csv(alt_out / "interval_report.csv")
        np.testing.assert_allclose(
            interval_report[["interval_coverage", "mean_width"]].astype(float),
            expected_interval_report[["interval_coverage", "mean_width"]].astype(float),
            atol=5e-6,
        )

        expected_neighbors = expected_neighbor_evidence(public_data, mutated_config, roles, mutated_policies)
        neighbor_report = pd.read_csv(alt_out / "neighbor_evidence.csv")
        pd.testing.assert_frame_equal(neighbor_report, expected_neighbors, check_dtype=False, atol=5e-6)

        expected_stress = expected_feature_pair_stress(public_data, mutated_config, roles, mutated_policies)
        stress_report = pd.read_csv(alt_out / "feature_pair_stress_report.csv")
        assert stress_report[["rank", "feature_a", "feature_b"]].astype(str).values.tolist() == expected_stress[
            ["rank", "feature_a", "feature_b"]
        ].astype(str).values.tolist()
        numeric_columns = [
            "baseline_mean_prediction",
            "stressed_mean_prediction",
            "mean_prediction_shift",
            "mean_abs_prediction_shift",
            "max_abs_prediction_shift",
        ]
        np.testing.assert_allclose(
            stress_report[numeric_columns].astype(float),
            expected_stress[numeric_columns].astype(float),
            atol=5e-6,
        )
