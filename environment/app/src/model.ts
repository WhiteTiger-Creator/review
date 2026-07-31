import * as tf from "@tensorflow/tfjs";
import type { FeatureRow } from "./features.js";

export async function trainLogisticModel(rows: FeatureRow[]): Promise<tf.LayersModel> {
  throw new Error("trainLogisticModel is not implemented — see incident report for class-balanced training requirements");
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
