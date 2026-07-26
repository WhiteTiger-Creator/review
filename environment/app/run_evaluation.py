"""
Fleet Readiness Evaluation Pipeline — Main Entry Point
Orchestrates the full evaluation: load → preprocess → calibrate → score → report.
"""

import os

import numpy as np
import pandas as pd
from eval.calibration import calibrate_confidence
from eval.metrics import (
    compute_confusion_matrix,
    compute_fleet_score,
    compute_per_class_metrics,
    compute_temporal_weights,
)
from eval.reporter import generate_report, write_report
from model.loader import load_config, load_ground_truth, load_predictions
from model.preprocessor import preprocess


def run_evaluation():
    """Execute the complete evaluation pipeline."""
    # Load data and configuration
    config = load_config()
    predictions = load_predictions()
    ground_truth = load_ground_truth()

    # Preprocess: temporal split + deduplication
    processed = preprocess(predictions, config)

    # Apply confidence calibration
    calibrated = calibrate_confidence(
        processed["confidence"].values,
        config["temperature"]
    )
    processed = processed.copy()
    processed["calibrated_confidence"] = calibrated

    # Compute temporal decay weights
    cutoff = pd.Timestamp(config["cutoff_date"])
    ages = (cutoff - processed["prediction_date"]).dt.days.values.astype(float)
    ages = np.abs(ages)  # absolute age in days
    temporal_weights = compute_temporal_weights(ages, config["half_life_days"])
    processed["temporal_weight"] = temporal_weights

    # Cold-start exclusion: count predictions per asset BEFORE dedup
    # (dedup already applied, so count remaining per asset)
    asset_counts = predictions.groupby("asset_id").size()

    # Determine which assets are excluded from aggregate
    min_preds = config["min_predictions"]
    excluded_assets = []
    included_assets = []

    for _, row in processed.iterrows():
        asset_id = row["asset_id"]
        true_class = ground_truth.get(asset_id, "operational")
        detail = {
            "asset_id": asset_id,
            "predicted_class": row["predicted_class"],
            "true_class": true_class,
            "confidence": float(row["confidence"]),
            "calibrated_confidence": float(row["calibrated_confidence"]),
            "temporal_weight": float(row["temporal_weight"]),
            "priority": int(row["priority"]),
        }

        # Check cold-start: use original prediction count
        orig_count = int(asset_counts.get(asset_id, 0))
        if orig_count < min_preds:
            excluded_assets.append(detail)
        else:
            included_assets.append(detail)

    # Compute metrics on included assets only
    if included_assets:
        pred_classes = [a["predicted_class"] for a in included_assets]
        true_classes = [a["true_class"] for a in included_assets]
    else:
        pred_classes = []
        true_classes = []

    per_class_metrics = compute_per_class_metrics(pred_classes, true_classes)
    confusion_mat = compute_confusion_matrix(pred_classes, true_classes)

    # Fleet aggregate score
    fleet_score = compute_fleet_score(
        included_assets, config["class_weights"], config
    )

    # Generate and write report
    all_details = [d for d in included_assets + excluded_assets]
    report = generate_report(
        per_class_metrics, confusion_mat, fleet_score,
        all_details, config, config["class_weights"], excluded_assets
    )
    write_report(report)

    print(f"Evaluation complete. Fleet score: {fleet_score:.4f}")
    print("Report written to /app/output/eval_report.json")


if __name__ == "__main__":
    os.makedirs("/app/output", exist_ok=True)
    run_evaluation()
