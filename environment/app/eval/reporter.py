"""
Evaluation report generator.
Assembles final evaluation report from computed metrics and fleet scores.
"""

import json

import numpy as np


def generate_report(per_class_metrics, confusion_matrix, fleet_score,
                    asset_details, config, class_weights, excluded_assets):
    """Generate the complete evaluation report JSON structure."""

    # Compute weighted and macro averages
    weighted_f1 = 0.0
    weight_sum = 0.0
    f1_values = []

    for cls, m in per_class_metrics.items():
        cw = class_weights.get(cls, 0.1)
        weighted_f1 += cw * m["f1"]
        weight_sum += cw
        f1_values.append(m["f1"])

    if weight_sum > 0:
        weighted_f1 = weighted_f1 / weight_sum
    macro_f1 = float(np.mean(f1_values)) if f1_values else 0.0

    report = {
        "metrics": {
            "per_class": {},
            "weighted_f1": round(weighted_f1, 4),
            "macro_f1": round(macro_f1, 4),
        },
        "fleet_score": round(fleet_score, 4),
        "confusion_matrix": confusion_matrix.tolist(),
        "asset_details": asset_details,
        "excluded_assets": excluded_assets,
        "config_used": {
            "temperature": config["temperature"],
            "half_life_days": config["half_life_days"],
            "min_predictions": config["min_predictions"],
            "cutoff_date": config["cutoff_date"],
            "class_weights": class_weights,
        }
    }

    for cls, m in per_class_metrics.items():
        report["metrics"]["per_class"][cls] = {
            "precision": round(m["precision"], 4),
            "recall": round(m["recall"], 4),
            "f1": round(m["f1"], 4),
        }

    return report


def write_report(report, output_path="/app/output/eval_report.json"):
    """Write the evaluation report to disk."""
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
