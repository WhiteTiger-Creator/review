"""Independent reference metrics for escalation reproduction verification (v2 postmortem)."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

APP = Path("/app")
SEED_SQL = APP / "data" / "featurestore.sql"
EXCLUDED = {"internal_test", "spam_quarantine"}
PRIORITY_SCORE = {"low": 1, "medium": 2, "high": 3, "urgent": 4}
TOLERANCE = 0.02
EPS = 1e-15

TICKET_RE = re.compile(
    r"\('(T-\d+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)',\s*([\d.]+),\s*(\d+),\s*'([^']+)'\)"
)
REPLAY_RE = re.compile(r"\('(T-\d+)',\s*'(\{.*\})'::jsonb")


def _load_rows() -> tuple[list[dict], list[dict]]:
    """Load tickets and api replays from the seed featurestore.sql, and split into train/holdout."""
    text = SEED_SQL.read_text(encoding="utf-8")
    tickets: list[dict] = []
    replays: dict[str, dict] = {}
    for match in TICKET_RE.finditer(text):
        ticket_id, created_at, channel, priority, resolved_hours, escalated, cohort = match.groups()
        tickets.append(
            {
                "ticket_id": ticket_id,
                "created_at": created_at,
                "channel": channel,
                "priority": priority,
                "resolved_hours": float(resolved_hours),
                "escalated": int(escalated),
                "cohort": cohort,
            }
        )
    for match in REPLAY_RE.finditer(text):
        ticket_id, body = match.groups()
        replays[ticket_id] = json.loads(body)
    rows: list[dict] = []
    for ticket in tickets:
        replay = replays.get(ticket["ticket_id"])
        if replay is None:
            continue
        latency = float(replay["features"]["api_latency_ms"])
        rows.append({**ticket, "api_latency_ms": latency})
    train = [r for r in rows if r["cohort"] == "train_jan" and r["channel"] not in EXCLUDED]
    holdout = [
        r
        for r in rows
        if r["cohort"] == "holdout_jan"
        and r["channel"] not in EXCLUDED
        and "2025-01-15" <= r["created_at"][:10] <= "2025-01-31"
    ]
    return train, holdout


def _features(row: dict) -> np.ndarray:
    """Extract numeric features array for a ticket row."""
    return np.array(
        [
            1.0,
            math.log1p(row["resolved_hours"]),
            float(PRIORITY_SCORE[row["priority"].lower().strip()]),
            1.0 if row["channel"] == "web" else 0.0,
            row["api_latency_ms"] / 100.0,
        ],
        dtype=np.float32,
    )


def _compute_class_weights(labels: np.ndarray) -> tuple[float, float]:
    """Compute inverse-frequency class weights: w_c = n_total / (n_classes * n_c)."""
    n = len(labels)
    n_pos = int(labels.sum())
    n_neg = n - n_pos
    w_neg = n / (2 * n_neg)
    w_pos = n / (2 * n_pos)
    return w_neg, w_pos


def _fit_logistic(train: list[dict], epochs: int = 50, lr: float = 0.01) -> np.ndarray:
    """Fit a logistic regression model with class-balanced weighting."""
    xs = np.stack([_features(r) for r in train]).astype(np.float32)
    ys = np.array([r["escalated"] for r in train], dtype=np.float32)
    n = xs.shape[0]

    # Class-balanced weights
    n_pos = int(ys.sum())
    n_neg = n - n_pos
    w_pos = n / (2 * n_pos)
    w_neg = n / (2 * n_neg)
    sample_weights = np.where(ys == 1, w_pos, w_neg).astype(np.float32)

    w = np.zeros(xs.shape[1], dtype=np.float32)
    for _ in range(epochs):
        z = xs @ w
        p = 1.0 / (1.0 + np.exp(-z))
        diff = p - ys
        weighted_diff = diff * sample_weights
        grad = (xs.T @ weighted_diff) / n
        w -= lr * grad
    return w


def _logits(w: np.ndarray, rows: list[dict]) -> np.ndarray:
    """Compute raw logits (before sigmoid)."""
    xs = np.stack([_features(r) for r in rows]).astype(np.float32)
    return (xs @ w).astype(np.float64)


def _find_optimal_temperature(logits: np.ndarray, labels: np.ndarray) -> float:
    """Grid search for optimal temperature on validation set."""
    best_t = 0.01
    best_nll = float("inf")
    for ti in range(1, 501):
        t = ti * 0.01
        p = 1.0 / (1.0 + np.exp(-logits / t))
        nll = -np.mean(labels * np.log(p + EPS) + (1 - labels) * np.log(1 - p + EPS))
        if nll < best_nll:
            best_nll = nll
            best_t = t
    return best_t


def _apply_temperature(logits: np.ndarray, temperature: float) -> np.ndarray:
    """Apply temperature scaling to logits."""
    return 1.0 / (1.0 + np.exp(-logits / temperature))


def _compute_macro_f1(proba: np.ndarray, labels: np.ndarray, threshold: float) -> float:
    """Compute macro-F1 (average of class-0 F1 and class-1 F1)."""
    preds = (proba >= threshold).astype(int)
    tp = int(((preds == 1) & (labels == 1)).sum())
    fp = int(((preds == 1) & (labels == 0)).sum())
    fn = int(((preds == 0) & (labels == 1)).sum())
    tn = int(((preds == 0) & (labels == 0)).sum())

    # Class 1
    prec1 = 0.0 if tp + fp == 0 else tp / (tp + fp)
    rec1 = 0.0 if tp + fn == 0 else tp / (tp + fn)
    f1_1 = 0.0 if prec1 + rec1 == 0 else 2 * prec1 * rec1 / (prec1 + rec1)

    # Class 0
    prec0 = 0.0 if tn + fn == 0 else tn / (tn + fn)
    rec0 = 0.0 if tn + fp == 0 else tn / (tn + fp)
    f1_0 = 0.0 if prec0 + rec0 == 0 else 2 * prec0 * rec0 / (prec0 + rec0)

    return (f1_0 + f1_1) / 2


def _find_optimal_threshold(proba: np.ndarray, labels: np.ndarray) -> float:
    """Find threshold maximizing macro-F1, tie-break: lowest threshold."""
    best_t = 0.01
    best_macro_f1 = -1.0
    for ti in range(1, 100):
        t = ti * 0.01
        mf1 = _compute_macro_f1(proba, labels, t)
        if mf1 > best_macro_f1:
            best_macro_f1 = mf1
            best_t = t
    return best_t


def _metrics(train: list[dict], holdout: list[dict]) -> dict:
    """Calculate full reproduction report metrics."""
    w = _fit_logistic(train)
    holdout_logits = _logits(w, holdout)
    labels = np.array([r["escalated"] for r in holdout], dtype=np.float64)
    train_labels = np.array([r["escalated"] for r in train], dtype=np.float64)

    # Temperature scaling
    temperature = _find_optimal_temperature(holdout_logits, labels)
    holdout_p = _apply_temperature(holdout_logits, temperature)

    # Threshold optimization
    threshold = _find_optimal_threshold(holdout_p, labels)

    # Confusion matrix
    preds = (holdout_p >= threshold).astype(int)
    labels_int = labels.astype(int)
    tp = int(((preds == 1) & (labels_int == 1)).sum())
    fp = int(((preds == 1) & (labels_int == 0)).sum())
    fn = int(((preds == 0) & (labels_int == 1)).sum())
    tn = int(((preds == 0) & (labels_int == 0)).sum())

    # Per-class metrics
    prec1 = 0.0 if tp + fp == 0 else tp / (tp + fp)
    rec1 = 0.0 if tp + fn == 0 else tp / (tp + fn)
    f1_1 = 0.0 if prec1 + rec1 == 0 else 2 * prec1 * rec1 / (prec1 + rec1)

    prec0 = 0.0 if tn + fn == 0 else tn / (tn + fn)
    rec0 = 0.0 if tn + fp == 0 else tn / (tn + fp)
    f1_0 = 0.0 if prec0 + rec0 == 0 else 2 * prec0 * rec0 / (prec0 + rec0)

    support0 = tn + fp
    support1 = tp + fn

    macro_f1 = (f1_0 + f1_1) / 2
    weighted_f1 = (f1_0 * support0 + f1_1 * support1) / (support0 + support1)

    # micro-F1
    micro_tp = tp + tn
    micro_fp = fp + fn
    micro_fn = fn + fp
    micro_prec = 0.0 if micro_tp + micro_fp == 0 else micro_tp / (micro_tp + micro_fp)
    micro_rec = 0.0 if micro_tp + micro_fn == 0 else micro_tp / (micro_tp + micro_fn)
    micro_f1 = 0.0 if micro_prec + micro_rec == 0 else 2 * micro_prec * micro_rec / (micro_prec + micro_rec)

    # Brier score
    brier = float(np.mean((holdout_p - labels) ** 2))

    # Calibration bins
    bins = []
    for i in range(10):
        lo = i / 10
        hi = (i + 1) / 10
        idx = np.minimum(9, np.maximum(0, np.floor(holdout_p * 10).astype(int)))
        mask = idx == i
        count = int(mask.sum())
        if count:
            predicted_mean = float(holdout_p[mask].mean())
            observed_rate = float(labels[mask].mean())
        else:
            predicted_mean = 0.0
            observed_rate = 0.0
        bins.append(
            {
                "bin_lo": round(lo, 1),
                "bin_hi": round(hi, 1),
                "predicted_mean": round(predicted_mean, 4),
                "observed_rate": round(observed_rate, 4),
                "count": count,
            }
        )

    # ECE
    n_holdout = len(holdout)
    ece = sum(
        (b["count"] / n_holdout) * abs(b["predicted_mean"] - b["observed_rate"])
        for b in bins
        if b["count"] > 0
    )

    # Class weights
    w_neg, w_pos = _compute_class_weights(train_labels)

    return {
        "model": "tfjs_logistic_regression",
        "temperature": round(temperature, 4),
        "optimal_threshold": round(threshold, 4),
        "holdout_n": len(holdout),
        "class_weights": {"0": round(w_neg, 4), "1": round(w_pos, 4)},
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "micro_f1": round(micro_f1, 4),
        "brier_score": round(brier, 4),
        "ece": round(ece, 4),
        "per_class": {
            "0": {
                "precision": round(prec0, 4),
                "recall": round(rec0, 4),
                "f1": round(f1_0, 4),
                "support": support0,
            },
            "1": {
                "precision": round(prec1, 4),
                "recall": round(rec1, 4),
                "f1": round(f1_1, 4),
                "support": support1,
            },
        },
        "calibration_bins": bins,
    }


def reference_report() -> dict:
    """Generate the complete reference report for the v2 postmortem metrics."""
    train, holdout = _load_rows()
    return _metrics(train, holdout)


def within_tolerance(actual: float, expected: float, tol: float = TOLERANCE) -> bool:
    """Check if the actual value is within the specified tolerance of the expected value."""
    return abs(actual - expected) <= tol
