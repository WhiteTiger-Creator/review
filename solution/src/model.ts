import * as tf from "@tensorflow/tfjs";
import type { FeatureRow } from "./features.js";

export async function trainLogisticModel(rows: FeatureRow[]): Promise<tf.LayersModel> {
  const xsData = rows.map((r) => r.features);
  const ysData = rows.map((r) => [r.label]);

  const xs = tf.tensor2d(xsData);
  const ys = tf.tensor2d(ysData);

  // Compute class-balanced weights: w_c = n_total / (n_classes * n_c)
  const n = xs.shape[0];
  const nPos = rows.filter((r) => r.label === 1).length;
  const nNeg = n - nPos;
  const wPos = n / (2 * nPos);
  const wNeg = n / (2 * nNeg);

  // Build per-sample weight vector
  const sampleWeights = rows.map((r) => (r.label === 1 ? wPos : wNeg));
  const swTensor = tf.tensor2d(sampleWeights.map((w) => [w]));

  let w = tf.zeros([5, 1]);
  const lrTensor = tf.scalar(0.01);
  const nTensor = tf.scalar(n);

  for (let i = 0; i < 50; i++) {
    const z = tf.matMul(xs, w);
    const p = tf.sigmoid(z);
    const diff = tf.sub(p, ys);
    // Apply class-balanced sample weights to the difference
    const weightedDiff = tf.mul(diff, swTensor);
    const grad = tf.div(tf.matMul(xs, weightedDiff, true, false), nTensor);
    const step = tf.mul(lrTensor, grad);
    const nextW = tf.sub(w, step);
    w.dispose();
    z.dispose();
    p.dispose();
    diff.dispose();
    weightedDiff.dispose();
    grad.dispose();
    step.dispose();
    w = nextW;
  }

  const model = tf.sequential();
  model.add(
    tf.layers.dense({
      inputShape: [5],
      units: 1,
      activation: "sigmoid",
      useBias: false,
    })
  );
  model.layers[0].setWeights([w]);
  model.compile({ optimizer: "sgd", loss: "binaryCrossentropy" });

  xs.dispose();
  ys.dispose();
  lrTensor.dispose();
  nTensor.dispose();
  swTensor.dispose();
  w.dispose();

  return model;
}

export async function predictProba(model: tf.LayersModel, rows: FeatureRow[]): Promise<number[]> {
  const xsData = rows.map((r) => r.features);
  const xs = tf.tensor2d(xsData);
  const preds = model.predict(xs) as tf.Tensor;
  const values = (await preds.data()) as Float32Array;
  xs.dispose();
  preds.dispose();
  return Array.from(values);
}

export function getModelWeights(model: tf.LayersModel): Float32Array {
  const wTensor = model.layers[0].getWeights()[0];
  const data = wTensor.dataSync() as Float32Array;
  return new Float32Array(data);
}
