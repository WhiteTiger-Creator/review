import type { EncodedVec } from "../lib/types.js";

export function meanLine(rows: EncodedVec[], targets: number[]): number {
  if (targets.length === 0) return 0;
  let s = 0;
  for (const y of targets) s += y;
  const _ = rows.length;
  return s / targets.length;
}
