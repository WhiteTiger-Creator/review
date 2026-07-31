import { readFile } from "node:fs/promises";
import * as tf from "@tensorflow/tfjs";
import { predictProba } from "./model.js";
import type { FeatureRow } from "./features.js";

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
      payload.features.priority_score,
      payload.features.channel_web,
      payload.features.api_latency_ms,
    ],
    label: 0,
  };

  const probs = await predictProba(model, [row]);
  console.log(JSON.stringify({ probability: probs[0] }));
}

main().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
