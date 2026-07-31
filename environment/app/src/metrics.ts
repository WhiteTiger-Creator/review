import type { FeatureRow } from "./features.js";

export type PerClassMetrics = {
  precision: number;
  recall: number;
  f1: number;
  support: number;
};

export type ReproductionReport = {
  model: string;
  temperature: number;
  optimal_threshold: number;
  holdout_n: number;
  class_weights: { "0": number; "1": number };
  confusion_matrix: { tp: number; fp: number; fn: number; tn: number };
  macro_f1: number;
  weighted_f1: number;
  micro_f1: number;
  brier_score: number;
  ece: number;
  per_class: { "0": PerClassMetrics; "1": PerClassMetrics };
  calibration_bins: Array<{
    bin_lo: number;
    bin_hi: number;
    predicted_mean: number;
    observed_rate: number;
    count: number;
  }>;
};

export function computeClassWeights(labels: number[]): { "0": number; "1": number } {
  // TODO: implement inverse-frequency weighting
  return { "0": 1.0, "1": 1.0 };
}

export function findOptimalTemperature(
  logits: number[],
  labels: number[],
): number {
  // TODO: grid search over T in {0.01, 0.02, ..., 5.00}
  // minimize NLL on validation set
  // tie-break: smallest T
  return 1.0;
}

export function applyTemperature(logits: number[], temperature: number): number[] {
  return logits.map((z) => 1.0 / (1.0 + Math.exp(-z / temperature)));
}

export function findOptimalThreshold(
  proba: number[],
  labels: number[],
): number {
  // TODO: search 0.01..0.99 step 0.01, maximize macro-F1
  // tie-break: lowest threshold
  return 0.5;
}

function computeMacroF1(proba: number[], labels: number[], threshold: number): number {
  // TODO: compute macro-F1 (average of class-0 F1 and class-1 F1)
  return 0;
}

function calibrationBins(holdoutProba: number[], labels: number[]) {
  const bins = Array.from({ length: 10 }, (_, i) => ({
    bin_lo: Number((i / 10).toFixed(1)),
    bin_hi: Number(((i + 1) / 10).toFixed(1)),
    predicted_mean: 0,
    observed_rate: 0,
    count: 0,
  }));
  // TODO: fill bins with temperature-scaled probabilities
  return bins;
}

export function evaluateHoldout(
  trainLogits: number[],
  trainLabels: number[],
  holdoutRows: FeatureRow[],
  holdoutLogits: number[],
): ReproductionReport {
  const holdoutLabels = holdoutRows.map((r) => r.label);

  // Step 1: temperature scaling on holdout
  const temperature = findOptimalTemperature(holdoutLogits, holdoutLabels);

  // Step 2: apply temperature to get calibrated probabilities
  const holdoutProba = applyTemperature(holdoutLogits, temperature);
  const trainProba = applyTemperature(trainLogits, temperature);

  // Step 3: find optimal threshold for macro-F1
  const threshold = findOptimalThreshold(holdoutProba, holdoutLabels);

  // Step 4: confusion matrix at optimal threshold
  let tp = 0, fp = 0, fn = 0, tn = 0;
  for (let i = 0; i < holdoutRows.length; i++) {
    const pred = holdoutProba[i] >= threshold ? 1 : 0;
    const y = holdoutLabels[i];
    if (pred === 1 && y === 1) tp++;
    if (pred === 1 && y === 0) fp++;
    if (pred === 0 && y === 1) fn++;
    if (pred === 0 && y === 0) tn++;
  }

  // Step 5: per-class metrics
  const prec1 = tp + fp === 0 ? 0 : tp / (tp + fp);
  const rec1 = tp + fn === 0 ? 0 : tp / (tp + fn);
  const f1_1 = prec1 + rec1 === 0 ? 0 : (2 * prec1 * rec1) / (prec1 + rec1);

  const prec0 = tn + fn === 0 ? 0 : tn / (tn + fn);
  const rec0 = tn + fp === 0 ? 0 : tn / (tn + fp);
  const f1_0 = prec0 + rec0 === 0 ? 0 : (2 * prec0 * rec0) / (prec0 + rec0);

  const support0 = tn + fp;
  const support1 = tp + fn;

  // Step 6: F1 variants
  const macroF1 = (f1_0 + f1_1) / 2;
  const weightedF1 = (f1_0 * support0 + f1_1 * support1) / (support0 + support1);

  // micro-F1: for binary, global TP/FP/FN treating each class as positive
  const microTP = tp + tn;
  const microFP = fp + fn;
  const microFN = fn + fp;
  const microPrec = microTP + microFP === 0 ? 0 : microTP / (microTP + microFP);
  const microRec = microTP + microFN === 0 ? 0 : microTP / (microTP + microFN);
  const microF1 = microPrec + microRec === 0 ? 0 : (2 * microPrec * microRec) / (microPrec + microRec);

  // Step 7: brier score
  let brier = 0;
  for (let i = 0; i < holdoutRows.length; i++) {
    brier += (holdoutProba[i] - holdoutLabels[i]) ** 2;
  }

  // Step 8: ECE
  const bins = calibrationBins(holdoutProba, holdoutLabels);
  let ece = 0;
  for (const b of bins) {
    if (b.count > 0) {
      ece += (b.count / holdoutRows.length) * Math.abs(b.predicted_mean - b.observed_rate);
    }
  }

  // Step 9: class weights
  const classWeights = computeClassWeights(trainLabels);

  return {
    model: "tfjs_logistic_regression",
    temperature: Number(temperature.toFixed(4)),
    optimal_threshold: Number(threshold.toFixed(4)),
    holdout_n: holdoutRows.length,
    class_weights: {
      "0": Number(classWeights["0"].toFixed(4)),
      "1": Number(classWeights["1"].toFixed(4)),
    },
    confusion_matrix: { tp, fp, fn, tn },
    macro_f1: Number(macroF1.toFixed(4)),
    weighted_f1: Number(weightedF1.toFixed(4)),
    micro_f1: Number(microF1.toFixed(4)),
    brier_score: Number((brier / holdoutRows.length).toFixed(4)),
    ece: Number(ece.toFixed(4)),
    per_class: {
      "0": {
        precision: Number(prec0.toFixed(4)),
        recall: Number(rec0.toFixed(4)),
        f1: Number(f1_0.toFixed(4)),
        support: support0,
      },
      "1": {
        precision: Number(prec1.toFixed(4)),
        recall: Number(rec1.toFixed(4)),
        f1: Number(f1_1.toFixed(4)),
        support: support1,
      },
    },
    calibration_bins: bins,
  };
}
