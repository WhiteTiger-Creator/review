# Fleet Readiness Evaluation Protocol v3.2

## 1. Overview

This document defines the evaluation protocol for the fleet readiness classification model. The pipeline processes prediction scores from batch inference runs, calibrates confidence values, applies temporal weighting, computes per-class and aggregate metrics, and produces a standardized evaluation report.

The protocol consists of six ordered stages. Each stage depends on ALL previous stages. The chain is not decomposable into independent steps.

1. **Preprocessing** — temporal filtering and deduplication
2. **Calibration** — Platt-scaling temperature adjustment
3. **Classification** — class assignment from calibrated scores
4. **Metric Computation** — per-class precision/recall/F1
5. **Fleet Aggregation** — weighted fleet readiness score with penalties
6. **Reporting** — structured output with precision requirements

---

## 2. Preprocessing Stage

### Rule R1: Temporal Split

Only predictions dated ON or AFTER the `cutoff_date` configuration parameter are retained for evaluation. Predictions before the cutoff belong to the training/validation window and must be excluded. The comparison is: `prediction_date >= cutoff_date`.

### Rule R2: Deduplication

After temporal filtering, if multiple predictions exist for the same `asset_id`, retain only the LATEST prediction (most recent `prediction_date`). Sort predictions by date ascending, then keep the LAST occurrence per asset. This ensures the most recent model assessment is used for each asset.

### Rule R3: Cold-Start Exclusion

Assets with fewer than `min_predictions` total predictions in the ORIGINAL dataset (before any filtering) are excluded from the aggregate fleet score computation. They are still included in the `asset_details` section of the report for reference, but do NOT contribute to per-class metrics or the fleet aggregate.

The `min_predictions` threshold is read from `eval_config.json`. The documented correct value is 3.

---

## 3. Calibration Stage

### Rule R4: Platt Scaling Temperature

Raw model confidence scores are calibrated using temperature scaling. The calibration formula is:

```
calibrated_confidence = raw_confidence / temperature
```

Where `temperature` is read from `eval_config.json`. The division operation reduces overconfident predictions (temperature > 1 shrinks confidences). Values are clipped to [0.0, 1.0] after calibration.

### Rule R5: Calibration Before Classification

Calibration MUST be applied before class assignment decisions. The class assignment uses calibrated confidence, not raw confidence.

---

## 4. Classification Stage

### Rule R6: Class Assignment

For the evaluation pipeline, the `predicted_class` field from the prediction batch is used directly as the model's class prediction. The calibrated confidence is used for scoring purposes but does not change the class assignment.

### Rule R7: Tie Breaking

When multiple predictions for the same asset have identical calibrated confidence (after dedup this shouldn't occur, but if it does), the prediction with higher `priority` value wins.

---

## 5. Metric Computation Stage

### Rule R8: Per-Class Metrics

For each of the four readiness classes (operational, degraded, critical, offline), compute:

- **Precision** = TP / (TP + FP), where TP = correctly predicted as this class, FP = incorrectly predicted as this class
- **Recall** = TP / (TP + FN), where FN = actually this class but predicted as something else
- **F1** = 2 × Precision × Recall / (Precision + Recall)

When a denominator is zero, the metric is 0.0.

### Rule R9: Weighted Average F1

```
weighted_f1 = sum(class_weight[c] * F1[c] for c in classes) / sum(class_weight[c] for c in classes)
```

Class weights are: operational=0.4, degraded=0.3, critical=0.2, offline=0.1.

### Rule R10: Macro Average F1

```
macro_f1 = mean(F1[c] for c in classes)
```

Simple unweighted arithmetic mean across all four classes.

### Rule R11: Confusion Matrix

A 4×4 integer matrix where rows represent predicted classes and columns represent actual (ground truth) classes. Row/column order follows: [operational, degraded, critical, offline].

### Rule R12: Temporal Decay Weighting

Predictions are weighted by recency using exponential decay:

```
weight = exp(-ln(2) × age_days / half_life_days)
```

Where:
- `age_days` = absolute number of days between prediction_date and cutoff_date
- `half_life_days` is from config (default 7.0)
- `ln(2)` ≈ 0.6931 ensures the weight halves every half_life_days period

The temporal weight is used in the fleet aggregate computation but does NOT affect per-class precision/recall/F1 (those are unweighted counts).

---

## 6. Fleet Aggregation Stage

### Rule R13: Fleet Readiness Score

The aggregate fleet readiness score combines calibrated confidence, class weights, and priority weights using MULTIPLICATIVE combination:

```
For each included asset:
    asset_contribution = calibrated_confidence × class_weight[predicted_class] × priority_weight
    where priority_weight = priority / 5.0

fleet_score = sum(asset_contributions) / sum(class_weight[predicted_class] × priority_weight)
```

The denominator uses the product of class_weight and priority_weight (multiplicative), NOT their sum.

### Rule R14: Penalty System

False-critical predictions (predicted_class = "critical" AND true_class = "operational") receive a penalty. The penalty INVERTS the contribution:

```
penalized_score = calibrated_confidence × penalty_multiplier
```

This inflated score is then clamped after normalization, effectively penalizing the aggregate.

### Rule R15: Normalization Ordering

Score normalization to [0.0, 1.0] range happens AFTER penalty application, not before. The sequence is:

1. Compute base score (calibrated_confidence)
2. Apply penalty multiplier for false-critical cases
3. Normalize the penalized score to [0, 1] via clamping
4. Apply weight combination

### Rule R16: Class Weight Values

The correct class weights for fleet evaluation are:

| Class | Weight |
|-------|--------|
| operational | 0.4 |
| degraded | 0.3 |
| critical | 0.2 |
| offline | 0.1 |

These MUST sum to 1.0.

---

## 7. Reporting Stage

### Rule R17: Output Schema

The output JSON at `/app/output/eval_report.json` must have this structure:

```json
{
    "metrics": {
        "per_class": {
            "operational": {"precision": <float>, "recall": <float>, "f1": <float>},
            "degraded": {"precision": <float>, "recall": <float>, "f1": <float>},
            "critical": {"precision": <float>, "recall": <float>, "f1": <float>},
            "offline": {"precision": <float>, "recall": <float>, "f1": <float>}
        },
        "weighted_f1": <float>,
        "macro_f1": <float>
    },
    "fleet_score": <float>,
    "confusion_matrix": [[int, ...], ...],
    "asset_details": [...],
    "excluded_assets": [...],
    "config_used": {...}
}
```

### Rule R18: Precision Requirements

- Per-class metrics: 4 decimal places
- weighted_f1, macro_f1: 4 decimal places
- fleet_score: 4 decimal places
- Confusion matrix values: integers

### Rule R19: Asset Detail Records

Each asset in `asset_details` includes:
- `asset_id`, `predicted_class`, `true_class`
- `confidence` (raw), `calibrated_confidence`
- `temporal_weight`, `priority`

### Rule R20: Excluded Assets

Assets excluded due to cold-start (Rule R3) appear in `excluded_assets` list with the same fields as asset_details. They do NOT appear in the aggregate computation.

---

## 8. Cross-Reference Interactions

These rules interact in non-obvious ways:

- **R1 + R2**: Temporal split BEFORE dedup means only recent predictions survive, then latest of THOSE is kept. Reversing order (dedup first) produces different results.
- **R2 + R3**: Dedup reduces prediction count per asset. Cold-start exclusion uses ORIGINAL counts (before filtering), not post-dedup counts.
- **R4 + R13**: Calibration changes confidence values → fleet score changes. Temperature > 1 shrinks scores.
- **R12 + R13**: Temporal weights affect fleet aggregate but NOT per-class metrics.
- **R14 + R15**: Penalty must happen before normalization. If normalized first, the penalty has no effect (already clamped to [0,1]).
- **R9 + R16**: Weighted F1 depends on correct class weights. Wrong weights → wrong weighted average even if per-class F1 is correct.
- **R13 + R16**: Fleet score uses multiplicative weight combination. Additive combination produces a fundamentally different scoring dynamic.
