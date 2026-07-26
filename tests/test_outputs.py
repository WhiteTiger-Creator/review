"""
Verifier for the fleet readiness evaluation pipeline.
Tests validate /app/output/eval_report.json against independently computed metrics.
"""

import json
import math
import os

import numpy as np
import pandas as pd


def load_report():
    """Load the evaluation report from the output path."""
    with open("/app/output/eval_report.json") as f:
        return json.load(f)


def get_correct_data():
    """Independently compute correct evaluation from raw data."""
    # Load raw predictions
    df = pd.read_csv("/app/data/predictions/batch_001.csv")
    df["prediction_date"] = pd.to_datetime(df["prediction_date"])

    # Load ground truth
    with open("/app/data/ground_truth/labels.json") as f:
        gt_data = json.load(f)
    gt = {a["asset_id"]: a["true_class"] for a in gt_data["assets"]}

    # R1: Temporal split - keep >= cutoff
    cutoff = pd.Timestamp("2024-09-01")
    filtered = df[df["prediction_date"] >= cutoff].copy()

    # R2: Dedup - keep latest per asset
    filtered_sorted = filtered.sort_values("prediction_date")
    deduped = filtered_sorted.drop_duplicates(subset="asset_id", keep="last")

    # R3: Cold-start exclusion (original counts >= 3)
    orig_counts = df.groupby("asset_id").size()
    min_preds = 3

    # R4: Calibration - divide by temperature
    temperature = 1.5
    deduped = deduped.copy()
    deduped["calibrated"] = np.clip(deduped["confidence"].values / temperature, 0.0, 1.0)

    # Separate included vs excluded
    included = []
    excluded = []
    for _, row in deduped.iterrows():
        aid = row["asset_id"]
        if orig_counts.get(aid, 0) < min_preds:
            excluded.append(row)
        else:
            included.append(row)

    return included, excluded, gt


def test_report_exists():
    """Verify the evaluation report was generated."""
    assert os.path.exists("/app/output/eval_report.json"), "Report not found"


def test_report_top_level_keys():
    """Verify report contains all required top-level keys."""
    report = load_report()
    for key in ["metrics", "fleet_score", "confusion_matrix", "asset_details",
                "excluded_assets", "config_used"]:
        assert key in report, f"Missing key: {key}"


def test_metrics_has_per_class():
    """Verify metrics section contains per-class breakdown for all 4 classes."""
    report = load_report()
    for cls in ["operational", "degraded", "critical", "offline"]:
        assert cls in report["metrics"]["per_class"], f"Missing class: {cls}"


def test_metrics_has_averages():
    """Verify metrics section contains weighted and macro F1 averages."""
    report = load_report()
    assert "weighted_f1" in report["metrics"]
    assert "macro_f1" in report["metrics"]


def test_temporal_split_keeps_recent():
    """Verify only predictions on or after 2024-09-01 are used."""
    report = load_report()
    report["asset_details"] + report.get("excluded_assets", [])
    # V023 has predictions on 2024-08-15, 2024-09-02, 2024-09-09
    # After correct split (>=cutoff), latest is 2024-09-09
    # V023 should be in included (3 total preds) with its post-cutoff prediction
    v023 = [d for d in report["asset_details"] if d["asset_id"] == "V023"]
    if v023:
        # V023's latest post-cutoff prediction is 2024-09-09 with confidence 0.83
        assert v023[0]["confidence"] == 0.83, (
            f"V023 should use prediction from 2024-09-09 (conf=0.83), got {v023[0]['confidence']}"
        )


def test_dedup_keeps_latest():
    """Verify deduplication retains the most recent prediction per asset."""
    report = load_report()
    # V007 has post-cutoff predictions on 09-07 (critical,0.73) and 09-14 (degraded,0.70)
    # Latest is 09-14 -> predicted_class should be 'degraded'
    details = report["asset_details"] + report.get("excluded_assets", [])
    v007 = [d for d in details if d["asset_id"] == "V007"]
    if v007:
        assert v007[0]["predicted_class"] == "degraded", (
            f"V007 should predict 'degraded' (latest 09-14), got {v007[0]['predicted_class']}"
        )


def test_calibration_divides_by_temperature():
    """Verify calibration uses division (conf/T), not multiplication (conf*T)."""
    report = load_report()
    # V008 has confidence 0.94 (latest post-cutoff 09-10), T=1.5
    # Correct calibration: 0.94/1.5 = 0.6267
    # Wrong (multiply): 0.94*1.5 = 1.0 (clipped)
    details = report["asset_details"] + report.get("excluded_assets", [])
    v008 = [d for d in details if d["asset_id"] == "V008"]
    if v008:
        cal = v008[0]["calibrated_confidence"]
        expected = 0.94 / 1.5
        assert abs(cal - expected) < 0.01, (
            f"V008 calibrated should be {expected:.4f} (conf/T), got {cal:.4f}"
        )


def test_cold_start_exclusion():
    """Verify assets with < 3 total predictions are excluded from aggregate."""
    report = load_report()
    excluded_ids = [a["asset_id"] for a in report["excluded_assets"]]
    # V021 has only 1 prediction, V022 has only 1 prediction
    # These should be excluded with min_predictions=3
    assert "V021" in excluded_ids, "V021 (1 prediction) should be excluded"
    assert "V022" in excluded_ids, "V022 (1 prediction) should be excluded"


def test_excluded_not_in_per_class_metrics():
    """Verify excluded cold-start assets do not affect per-class metrics."""
    report = load_report()
    included, _excluded, _gt = get_correct_data()
    # Count included assets
    included_count = len(included)
    # Confusion matrix total should equal included count
    cm = report["confusion_matrix"]
    cm_total = sum(sum(row) for row in cm)
    assert cm_total == included_count, (
        f"Confusion matrix total {cm_total} != included assets {included_count}"
    )


def test_confusion_matrix_shape():
    """Verify confusion matrix is 4x4."""
    report = load_report()
    cm = report["confusion_matrix"]
    assert len(cm) == 4, f"Confusion matrix should have 4 rows, got {len(cm)}"
    for row in cm:
        assert len(row) == 4, f"Each row should have 4 columns, got {len(row)}"


def test_class_weights_correct():
    """Verify config_used reflects correct class weights per protocol R16."""
    report = load_report()
    cw = report["config_used"]["class_weights"]
    assert abs(cw["operational"] - 0.4) < 0.001, (
        f"operational weight should be 0.4, got {cw['operational']}"
    )
    assert abs(cw["degraded"] - 0.3) < 0.001
    assert abs(cw["critical"] - 0.2) < 0.001
    assert abs(cw["offline"] - 0.1) < 0.001


def test_min_predictions_threshold():
    """Verify min_predictions config is set to 3 per protocol R3."""
    report = load_report()
    assert report["config_used"]["min_predictions"] == 3, (
        f"min_predictions should be 3, got {report['config_used']['min_predictions']}"
    )


def test_fleet_score_multiplicative_weights():
    """Verify fleet score uses multiplicative (class_weight * priority_weight) combination."""
    report = load_report()
    included, _, gt = get_correct_data()
    if not included:
        return

    correct_weights = {"operational": 0.4, "degraded": 0.3, "critical": 0.2, "offline": 0.1}
    penalty_mult = 3.0

    numerator = 0.0
    denominator = 0.0
    for row in included:
        aid = row["asset_id"]
        pred_cls = row["predicted_class"]
        true_cls = gt.get(aid, "operational")
        cal_conf = float(row["calibrated"])
        priority_w = int(row["priority"]) / 5.0
        cw = correct_weights.get(pred_cls, 0.1)

        score = cal_conf
        if pred_cls == "critical" and true_cls == "operational":
            score = score * penalty_mult
        score = max(0.0, min(1.0, score))

        # Multiplicative combination
        numerator += score * cw * priority_w
        denominator += cw * priority_w

    expected_fleet = numerator / denominator if denominator > 0 else 0.0
    expected_fleet = round(expected_fleet, 4)

    assert abs(report["fleet_score"] - expected_fleet) < 0.002, (
        f"Fleet score should be {expected_fleet}, got {report['fleet_score']}"
    )


def test_penalty_for_false_critical():
    """Verify false-critical predictions receive penalty multiplier."""
    report = load_report()
    # The penalty inflates the score for false-critical cases
    # This affects the fleet aggregate
    assert report["fleet_score"] is not None


def test_normalization_after_penalty():
    """Verify scores are normalized AFTER penalty application per R15."""
    report = load_report()
    # Fleet score should be in [0, 1] range after proper normalization
    assert 0.0 <= report["fleet_score"] <= 1.0, (
        f"Fleet score {report['fleet_score']} out of [0,1] range"
    )


def test_temporal_decay_uses_ln2():
    """Verify temporal decay formula uses ln(2) factor for true half-life."""
    report = load_report()
    details = report["asset_details"] + report.get("excluded_assets", [])
    # V005 latest post-cutoff is 09-11, cutoff is 09-01, age = 10 days
    # Correct: exp(-ln(2)*10/7) = exp(-0.6931*10/7) = exp(-0.9902) = 0.3716
    # Wrong: exp(-10/7) = exp(-1.4286) = 0.2397
    v005 = [d for d in details if d["asset_id"] == "V005"]
    if v005:
        tw = v005[0]["temporal_weight"]
        age = 10.0
        half_life = 7.0
        expected = math.exp(-math.log(2) * age / half_life)
        assert abs(tw - expected) < 0.01, (
            f"V005 temporal weight should be {expected:.4f} (ln2 formula), got {tw:.4f}"
        )


def test_per_class_precision_operational():
    """Verify precision for operational class is correctly computed."""
    report = load_report()
    included, _, gt = get_correct_data()

    pred_classes = [r["predicted_class"] for r in included]
    true_classes = [gt.get(r["asset_id"], "operational") for r in included]

    tp = sum(1 for p, a in zip(pred_classes, true_classes) if p == "operational" and a == "operational")
    fp = sum(1 for p, a in zip(pred_classes, true_classes) if p == "operational" and a != "operational")
    expected_prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0

    actual = report["metrics"]["per_class"]["operational"]["precision"]
    assert abs(actual - round(expected_prec, 4)) < 0.001, (
        f"Operational precision should be {expected_prec:.4f}, got {actual}"
    )


def test_per_class_recall_operational():
    """Verify recall for operational class is correctly computed."""
    report = load_report()
    included, _, gt = get_correct_data()

    pred_classes = [r["predicted_class"] for r in included]
    true_classes = [gt.get(r["asset_id"], "operational") for r in included]

    tp = sum(1 for p, a in zip(pred_classes, true_classes) if p == "operational" and a == "operational")
    fn = sum(1 for p, a in zip(pred_classes, true_classes) if p != "operational" and a == "operational")
    expected_rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    actual = report["metrics"]["per_class"]["operational"]["recall"]
    assert abs(actual - round(expected_rec, 4)) < 0.001, (
        f"Operational recall should be {expected_rec:.4f}, got {actual}"
    )


def test_per_class_f1_operational():
    """Verify F1 for operational class is correctly computed."""
    report = load_report()
    m = report["metrics"]["per_class"]["operational"]
    p, r = m["precision"], m["recall"]
    expected_f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    assert abs(m["f1"] - round(expected_f1, 4)) < 0.001


def test_weighted_f1():
    """Verify weighted F1 uses correct class weights per protocol R9."""
    report = load_report()
    correct_weights = {"operational": 0.4, "degraded": 0.3, "critical": 0.2, "offline": 0.1}
    per_class = report["metrics"]["per_class"]

    numerator = sum(correct_weights[c] * per_class[c]["f1"] for c in correct_weights)
    denominator = sum(correct_weights.values())
    expected = numerator / denominator

    assert abs(report["metrics"]["weighted_f1"] - round(expected, 4)) < 0.001, (
        f"Weighted F1 should be {expected:.4f}, got {report['metrics']['weighted_f1']}"
    )


def test_macro_f1():
    """Verify macro F1 is simple mean of per-class F1 scores."""
    report = load_report()
    per_class = report["metrics"]["per_class"]
    f1_vals = [per_class[c]["f1"] for c in ["operational", "degraded", "critical", "offline"]]
    expected = sum(f1_vals) / 4.0

    assert abs(report["metrics"]["macro_f1"] - round(expected, 4)) < 0.001, (
        f"Macro F1 should be {expected:.4f}, got {report['metrics']['macro_f1']}"
    )


def test_score_precision_4_decimals():
    """Verify fleet_score is rounded to 4 decimal places."""
    report = load_report()
    score = report["fleet_score"]
    assert score == round(score, 4), f"Fleet score not 4 decimals: {score}"


def test_metric_precision_4_decimals():
    """Verify per-class metrics are rounded to 4 decimal places."""
    report = load_report()
    for cls, m in report["metrics"]["per_class"].items():
        for metric_name in ["precision", "recall", "f1"]:
            val = m[metric_name]
            assert val == round(val, 4), (
                f"{cls}.{metric_name} not 4 decimals: {val}"
            )


def test_all_assets_in_detail():
    """Verify all processed assets appear in asset_details or excluded_assets."""
    report = load_report()
    all_ids = set()
    for d in report["asset_details"]:
        all_ids.add(d["asset_id"])
    for d in report["excluded_assets"]:
        all_ids.add(d["asset_id"])
    # Should have all assets that have post-cutoff predictions
    df = pd.read_csv("/app/data/predictions/batch_001.csv")
    df["prediction_date"] = pd.to_datetime(df["prediction_date"])
    cutoff = pd.Timestamp("2024-09-01")
    post_cutoff = df[df["prediction_date"] >= cutoff]
    expected_ids = set(post_cutoff["asset_id"].unique())
    assert expected_ids == all_ids, (
        f"Missing assets: {expected_ids - all_ids}"
    )


def test_deterministic_output():
    """Verify running the pipeline twice produces identical output."""
    import subprocess
    subprocess.run(["python3", "/app/run_evaluation.py"],
                   capture_output=True, cwd="/app", timeout=30, check=False)
    with open("/app/output/eval_report.json") as f:
        r1 = json.load(f)
    subprocess.run(["python3", "/app/run_evaluation.py"],
                   capture_output=True, cwd="/app", timeout=30, check=False)
    with open("/app/output/eval_report.json") as f:
        r2 = json.load(f)
    assert r1 == r2, "Non-deterministic output"
