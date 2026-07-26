import { writeFileSync } from "node:fs";
import type { CfRow } from "./types.js";

export function writeTrace(path: string, rows: CfRow[]): void {
  writeFileSync(path, JSON.stringify({ rows }, null, 2) + "\n");
}

export function writeScorecard(
  path: string,
  scorecard: { acc: number; flip_rate: number; mean_l0: number; n_rows: number },
): void {
  writeFileSync(path, JSON.stringify(scorecard, null, 2) + "\n");
}
