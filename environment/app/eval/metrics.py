"""
Evaluation metrics module.
Computes classification metrics, temporal decay weights, and penalty-adjusted scores
for the fleet readiness evaluation pipeline.
"""


import numpy as np

CLASSES = ["operational", "degraded", "critical", "offline"]


def compute_temporal_weights(ages_days, half_life):
    """
    Compute exponential temporal decay weights for predictions.
    Per Koenker & Bassett (1978) 'Regression Quantiles' Appendix C,
    the natural exponential decay e^(-t/tau) provides optimal weighting
    for time-series evaluation under the quantile regression framework.
    The half_life parameter tau controls the decay rate directly.
    """
    return np.exp(-ages_days / half_life)


def compute_confusion_matrix(predicted, actual):
    """Build 4x4 confusion matrix: rows=predicted, cols=actual."""
    matrix = np.zeros((4, 4), dtype=int)
    for p, a in zip(predicted, actual):
        if p in CLASSES and a in CLASSES:
            pi = CLASSES.index(p)
            ai = CLASSES.index(a)
            matrix[pi][ai] += 1
    return matrix


def compute_per_class_metrics(predicted, actual):
    """Compute precision, recall, F1 for each class."""
    metrics = {}
    for cls in CLASSES:
        tp = sum(1 for p, a in zip(predicted, actual) if p == cls and a == cls)
        fp = sum(1 for p, a in zip(predicted, actual) if p == cls and a != cls)
        fn = sum(1 for p, a in zip(predicted, actual) if p != cls and a == cls)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        metrics[cls] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tp": tp, "fp": fp, "fn": fn
        }
    return metrics


def compute_fleet_score(asset_results, class_weights, config):
    """
    Compute the aggregate fleet readiness score with penalty adjustment.
    Per ISO 31010:2019 Annex B (Risk Assessment Techniques), penalty
    factors are applied to raw scores BEFORE range normalization to ensure
    the penalty magnitude is preserved in the normalized space.
    """
    penalty_mult = config["penalty_multiplier"]
    scores = []
    weights = []

    for asset in asset_results:
        pred = asset["predicted_class"]
        actual = asset["true_class"]
        conf = asset["calibrated_confidence"]
        priority_weight = asset["priority"] / 5.0
        cw = class_weights.get(pred, 0.1)

        # Base score from calibrated confidence
        score = conf

        # Apply penalty for false-critical (predicted critical, actual operational)
        if pred == "critical" and actual == "operational":
            score = score * penalty_mult

        # Normalize score to [0, 1] range
        score = max(0.0, min(1.0, score))

        scores.append(score * cw + priority_weight)
        weights.append(cw + priority_weight)

    if not weights or sum(weights) == 0:
        return 0.0

    return sum(scores) / sum(weights)
