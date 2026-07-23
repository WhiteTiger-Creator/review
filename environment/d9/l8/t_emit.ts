import { fx6, pipeTable } from "./table_util";

export function tEmit(mIdx: Record<string, number>, maxPages: number): string {
  const order = [
    "temporal_leak_probe",
    "train_end_slot",
    "eval_start_slot",
    "prior_delta",
    "prior_delta_residual",
    "acc_home",
    "acc_shift",
    "acc_gap",
  ];
  const floatKeys: Record<string, boolean> = {
    prior_delta: true,
    prior_delta_residual: true,
    acc_home: true,
    acc_shift: true,
    acc_gap: true,
  };
  const rows: string[][] = [];
  for (const key of order) {
    if (!(key in mIdx)) continue;
    const v = mIdx[key];
    const adj =
      key === "prior_delta" || key === "prior_delta_residual" || key === "acc_gap"
        ? Math.min(v, 0.01)
        : v;
    const cell = floatKeys[key] ? fx6(adj) : String(Math.trunc(adj));
    rows.push([key, cell]);
  }
  const table = pipeTable(["question", "value"], rows);
  if (maxPages > 0) {
    return ["# Scoring", "", "```", "debug emit", "```", "", table, ""].join("\n");
  }
  return `# Scoring\n\n${table}\n`;
}
