# January 2025 Support Escalation Model Incident Report

Incident ID: INC-2025-0142 · Owner: Support ML Platform · Status: Closed (postmortem published)

On 31 January 2025, the on-call rotation observed elevated false-negative rates on the ticket escalation scorer that routes urgent customer issues to tier-2. The scorer is a TensorFlow.js logistic regression model trained on PGlite feature-store tables (`tickets`, `api_replay`). This document is the authoritative narrative for cohort policy, threshold history, class-weighting rules, temperature-scaling procedure, and the holdout calibration table auditors expect reproduced from source data.

## Executive Summary

The January model used five numeric features derived from ticket metadata and the latest API replay row per ticket:
- Intercept (always 1.0)
- `log1p(resolved_hours)`
- `priority_score` (low=1, medium=2, high=3, urgent=4). Priority values must be trimmed and parsed case-insensitively (e.g. `" HIGH "` or `"High"` maps to `3`).
- `channel_web` indicator (1 if channel is web, else 0)
- `api_latency_ms` scaled exactly as `api_latency_ms / 100.0`

### Training Setup and Deterministic Requirements

For exact audit reproducibility, the training process must be fully deterministic and configured as follows:
- **Optimizer/Algorithm**: Manual batch gradient descent with class-balanced sample weighting (no external library optimizers, no feature standardization).
- **Epochs**: Exactly 50 epochs.
- **Learning Rate**: Exactly 0.01.
- **Weights Initialization**: Initialized to all zeros.
- **Class-Balanced Loss**: The v2 postmortem identified that class imbalance in the training data contributed to the false-negative drift. The corrective measure is to apply inverse-frequency class weights during gradient computation. For a binary problem with `n_total` samples, `n_pos` positive and `n_neg` negative samples, the weights are:
  - `w_pos = n_total / (2 * n_pos)`
  - `w_neg = n_total / (2 * n_neg)`
  Each sample's gradient contribution `(p_i - y_i) * x_i` is multiplied by the weight of its class.

### Post-Hoc Temperature Scaling

The v2 postmortem introduced mandatory temperature scaling to improve probability calibration. Temperature scaling is applied **after** model training using the **holdout (validation) split only**:

1. Compute raw logits for each holdout sample: `z_i = w · x_i`
2. Grid-search over temperature values `T ∈ {0.01, 0.02, 0.03, ..., 5.00}` (exactly 500 candidates, stepping by 0.01)
3. For each candidate `T`, compute scaled probabilities: `p_i = sigmoid(z_i / T)`
4. Compute the negative log-likelihood (NLL) of the holdout labels under these scaled probabilities: `NLL = -mean(y_i * log(p_i + eps) + (1 - y_i) * log(1 - p_i + eps))` where `eps = 1e-15`
5. Select the `T` that minimizes NLL. On ties (identical NLL values), choose the **smallest** `T`.
6. Apply the selected `T` to all subsequent probability computations (training set probabilities, holdout set probabilities, and scoring requests).

The selected temperature must be reported as `temperature` in the output.

### Threshold Optimization for Macro-F1

Instead of using a fixed percentile threshold, the v2 policy optimizes the probability threshold to maximize **macro-F1** on the holdout set:

1. Candidates: `{0.01, 0.02, 0.03, ..., 0.99}` (exactly 99 thresholds, stepping by 0.01)
2. For each candidate threshold `t`:
   - Compute binary predictions: `ŷ_i = 1 if p_i >= t, else 0`
   - Compute macro-F1: average of F1 for class 0 and F1 for class 1
   - Class-k F1: `2 * precision_k * recall_k / (precision_k + recall_k)`, or 0 if denominator is 0
   - Class 1: precision = TP/(TP+FP), recall = TP/(TP+FN)
   - Class 0: precision = TN/(TN+FN), recall = TN/(TN+FP)
3. Select the threshold `t` that maximizes macro-F1. On ties, choose the **lowest** threshold.

Note: Macro-F1 requires computing F1 for BOTH classes. This differs from "regular" binary F1 which only considers the positive class.

### Cohort Definitions and Exclusions
1. **Exclusions**: The escalation policy excludes `internal_test` and `spam_quarantine` channels from both the training and holdout cohorts.
2. **Training Cohort**: Tickets tagged with `cohort = 'train_jan'`.
3. **Holdout Cohort**: Tickets tagged with `cohort = 'holdout_jan'` with `created_at` between `2025-01-15T00:00:00` and `2025-01-31T23:59:59` inclusive.

## Metric Definitions

### Scalar Metrics
- **macro_f1**: Average of per-class F1 scores (class 0 F1 and class 1 F1) at the optimized threshold.
- **weighted_f1**: Weighted average of per-class F1 scores, where each class F1 is weighted by its support (number of samples in that class) in the holdout set.
- **micro_f1**: Computed from global TP, FP, FN counts across all classes. For binary classification, micro-F1 equals accuracy only when treating both classes symmetrically.
- **brier_score**: Mean squared error between temperature-scaled predicted probabilities and actual labels.
- **ece**: Expected Calibration Error computed as the weighted average of |predicted_mean - observed_rate| across bins, weighted by bin count / total count.

### Per-Class Metrics
For each class (0 and 1), report:
- **precision**: TP_k / (TP_k + FP_k), or 0 if denominator is 0
- **recall**: TP_k / (TP_k + FN_k), or 0 if denominator is 0  
- **f1**: harmonic mean of precision and recall, or 0 if both are 0
- **support**: number of holdout samples in this class

Where TP_k, FP_k, FN_k are computed treating class k as the positive class.

### Calibration Bins
Ten equal-width bins on [0, 1] with `predicted_mean`, `observed_rate`, and `count` per bin. Bins are defined on ranges: `[0.0, 0.1)`, `[0.1, 0.2)`, ..., `[0.9, 1.0]`. Computed using temperature-scaled probabilities.

### Confusion Matrix
The full 2×2 confusion matrix: `tp`, `fp`, `fn`, `tn` — computed at the optimized threshold using temperature-scaled probabilities.

### Class Weights
Report the computed class weights as `class_weights: {"0": w_neg, "1": w_pos}` in the output.