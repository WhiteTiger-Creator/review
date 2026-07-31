import { readFile } from "node:fs/promises";
import * as tf from "@tensorflow/tfjs";
import { PRIORITY_SCORE, type FeatureRow } from "./features.js";

async function main(): Promise<void> {
  const payloadPath = process.argv[2];
  if (!payloadPath) {
    console.error("Usage: node score.js <payload-path>");
    process.exit(1);
  }
  const payloadRaw = await readFile(payloadPath, "utf8");
  const payload = JSON.parse(payloadRaw);

  const model = await tf.loadLayersModel({
    load: async () => {
      const modelJsonRaw = await readFile("/app/artifacts/model/model.json", "utf8");
      const modelJson = JSON.parse(modelJsonRaw);
      const weightDataRaw = await readFile("/app/artifacts/model/weights.bin");
      const weightData = weightDataRaw.buffer.slice(
        weightDataRaw.byteOffset,
        weightDataRaw.byteOffset + weightDataRaw.byteLength
      );
      return {
        modelTopology: modelJson.modelTopology,
        weightSpecs: modelJson.weightsManifest[0].weights,
        weightData: weightData
      };
    }
  });

  const row: FeatureRow = {
    ticket_id: payload.ticket_id,
    channel: payload.channel,
    priority: payload.priority,
    resolved_hours: payload.resolved_hours,
    escalated: 0,
    cohort: "",
    api_latency_ms: payload.features.api_latency_ms,
    features: [
      1,
      payload.features.log_resolved_hours,
      PRIORITY_SCORE[(payload.priority || "").toLowerCase().trim()] ?? payload.features.priority_score ?? 0,
      payload.features.channel_web,
      payload.features.api_latency_ms / 100.0,
    ],
    label: 0,
  };

  let temperature = 1.0;
  try {
    const reproRaw = await readFile("/app/artifacts/reproduction.json", "utf8");
    const repro = JSON.parse(reproRaw);
    if (typeof repro.temperature === "number" && repro.temperature > 0) {
      temperature = repro.temperature;
    }
  } catch {
    // Default to 1.0 if reproduction artifact does not exist
  }

  const weightsTensor = model.layers[0].getWeights()[0];
  const weights = await weightsTensor.data();
  let z = 0;
  for (let i = 0; i < row.features.length; i++) {
    z += row.features[i] * weights[i];
  }
  const prob = 1.0 / (1.0 + Math.exp(-z / temperature));

  console.log(JSON.stringify({ probability: prob }));
}

main().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
