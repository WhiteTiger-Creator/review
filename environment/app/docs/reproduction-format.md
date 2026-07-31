# reproduction.json contract (v2 postmortem)

Path: `/app/artifacts/reproduction.json`

## Required top-level fields

| field | type | notes |
|---|---|---|
| `model` | string | must be `tfjs_logistic_regression` |
| `temperature` | number | optimal temperature from grid search (> 0) |
| `optimal_threshold` | number | threshold maximizing macro-F1 on validation |
| `holdout_n` | integer | filtered holdout ticket count |
| `class_weights` | object | inverse-frequency class weights `{"0": w_neg, "1": w_pos}` |
| `confusion_matrix` | object | `{"tp": int, "fp": int, "fn": int, "tn": int}` at optimal threshold |
| `macro_f1` | number | average of per-class F1 scores |
| `weighted_f1` | number | support-weighted average of per-class F1 scores |
| `micro_f1` | number | F1 from global TP/FP/FN counts |
| `brier_score` | number | mean squared error of temperature-scaled probabilities |
| `ece` | number | Expected Calibration Error |
| `per_class` | object | per-class precision, recall, f1, support |
| `calibration_bins` | array | exactly 10 bins |

## class_weights

Inverse-frequency class weights: `w_c = n_total / (n_classes * n_c)`.

```json
{
  "0": 1.0234,
  "1": 0.9789
}
```

## confusion_matrix

Full 2×2 confusion matrix at the optimized threshold:

```json
{
  "tp": 450,
  "fp": 120,
  "fn": 80,
  "tn": 449
}
```

The sum `tp + fp + fn + tn` must equal `holdout_n`.

## per_class

Per-class metrics for each class (0 = not escalated, 1 = escalated):

```json
{
  "0": { "precision": 0.8491, "recall": 0.7893, "f1": 0.8181, "support": 569 },
  "1": { "precision": 0.7895, "recall": 0.8491, "f1": 0.8182, "support": 530 }
}
```

Class-k metrics treat class k as the "positive" class:
- Class 1: TP = correctly predicted escalations, FP = false escalations, FN = missed escalations
- Class 0: TP = correctly predicted non-escalations (TN in the standard matrix), FP = missed escalations (FN), FN = false escalations (FP)

## calibration_bins element

Each element must include `bin_lo`, `bin_hi`, `predicted_mean`, `observed_rate`, and `count`. Computed using temperature-scaled probabilities.

## Scoring payload shape

Fixture requests under `/app/fixtures/scoring-requests/` use:

```json
{
  "ticket_id": "string",
  "channel": "string",
  "priority": "string",
  "resolved_hours": 0.0,
  "features": {
    "log_resolved_hours": 0.0,
    "priority_score": 0,
    "channel_web": 0,
    "api_latency_ms": 0.0
  }
}
```

---

## Numeric Rounding Convention

All numeric outputs use JavaScript's `Number.toFixed(N)` method followed by `Number()` conversion:

```typescript
Number(value.toFixed(4))  // for all floating-point metrics
Number(value.toFixed(1))  // for bin_lo, bin_hi
```

---

## Output File Encoding and Format

The output file must be:

1. **Encoding:** UTF-8. No BOM.
2. **Line endings:** Any (LF or CRLF).
3. **Trailing newline:** Required.
4. **Indentation:** `JSON.stringify(report, null, 2)` uses 2-space indentation.
5. **Field ordering:** Follows `ReproductionReport` type definition.

---

## Temperature Scaling Details

Temperature scaling is a post-hoc calibration technique applied after model training:
1. Compute raw logits `z_i = w · x_i` for each sample
2. Grid-search temperature `T ∈ {0.01, 0.02, ..., 5.00}` minimizing NLL on holdout
3. Apply: `p_i = sigmoid(z_i / T)`
4. Tie-break: smallest T

The temperature parameter **must** be optimized on the holdout/validation split only. Using training data for temperature optimization would be incorrect.

---

## Threshold Optimization Details

Instead of a fixed percentile threshold, the v2 policy optimizes the probability threshold:
1. Search candidates: `{0.01, 0.02, ..., 0.99}` (99 values)
2. For each candidate, compute macro-F1 = (F1_class0 + F1_class1) / 2
3. Select threshold maximizing macro-F1
4. Tie-break: lowest threshold

Note: macro-F1 is NOT the same as the "regular" F1 score for the positive class. It requires computing F1 for both classes and averaging.

---

## F1 Variant Definitions

### Macro-F1
Average of per-class F1: `(F1_class0 + F1_class1) / 2`

### Weighted-F1
Support-weighted average: `(F1_class0 × support_0 + F1_class1 × support_1) / (support_0 + support_1)`

### Micro-F1
For binary classification with symmetric one-vs-rest decomposition:
- micro_TP = TP + TN (true positives from both one-vs-rest views)
- micro_FP = FP + FN
- micro_FN = FN + FP
- micro_precision = micro_TP / (micro_TP + micro_FP)
- micro_recall = micro_TP / (micro_TP + micro_FN)
- micro_F1 = 2 × micro_precision × micro_recall / (micro_precision + micro_recall)

---

## ECE (Expected Calibration Error)

ECE = Σ (count_b / N) × |predicted_mean_b - observed_rate_b|

where the sum is over all non-empty calibration bins, and N is the total holdout count.

---

*End of reproduction-format.md. This document is the authoritative output contract for the v2 January 2025 escalation model audit.*
