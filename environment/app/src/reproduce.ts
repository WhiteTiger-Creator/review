import { mkdir, writeFile } from "node:fs/promises";
import { loadDatabase } from "./db.js";
import { buildFeatureRows } from "./features.js";
import { trainLogisticModel, predictProba, getModelWeights } from "./model.js";
import { evaluateHoldout } from "./metrics.js";

async function main(): Promise<void> {
  const db = await loadDatabase();
  const trainRows = await buildFeatureRows(db, "train_jan");
  const holdoutRows = await buildFeatureRows(db, "holdout_jan");
  const model = await trainLogisticModel(trainRows);
  const trainProba = await predictProba(model, trainRows);
  const holdoutProba = await predictProba(model, holdoutRows);

  // Get raw logits for temperature scaling
  const weights = getModelWeights(model);
  const trainLogits = trainRows.map((r) => {
    let z = 0;
    for (let j = 0; j < r.features.length; j++) z += r.features[j] * weights[j];
    return z;
  });
  const holdoutLogits = holdoutRows.map((r) => {
    let z = 0;
    for (let j = 0; j < r.features.length; j++) z += r.features[j] * weights[j];
    return z;
  });

  const trainLabels = trainRows.map((r) => r.label);
  const report = evaluateHoldout(trainLogits, trainLabels, holdoutRows, holdoutLogits);

  await mkdir("/app/artifacts", { recursive: true });
  await mkdir("/app/artifacts/model", { recursive: true });
  await model.save({
    save: async (modelArtifacts) => {
      const modelJson = {
        modelTopology: modelArtifacts.modelTopology,
        weightsManifest: [{
          paths: ["weights.bin"],
          weights: modelArtifacts.weightSpecs
        }]
      };
      await writeFile("/app/artifacts/model/model.json", JSON.stringify(modelJson, null, 2), "utf8");
      if (modelArtifacts.weightData) {
        const buffer = Buffer.from(new Uint8Array(modelArtifacts.weightData as ArrayBuffer));
        await writeFile("/app/artifacts/model/weights.bin", buffer);
      }
      return {
        modelArtifactsInfo: {
          dateSaved: new Date(),
          modelTopologyType: "JSON"
        }
      };
    }
  });
  await writeFile("/app/artifacts/reproduction.json", `${JSON.stringify(report, null, 2)}\n`, "utf8");
}

main().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
