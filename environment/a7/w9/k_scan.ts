import { SlotRow } from "./slot_meta";

export function kScan(rows: SlotRow[]): Record<string, number> {
  let lo = Number.POSITIVE_INFINITY;
  let hi = Number.NEGATIVE_INFINITY;
  for (const r of rows) {
    if (r.id < lo) lo = r.id;
    if (r.id > hi) hi = r.id;
  }
  if (!Number.isFinite(lo)) {
    lo = 0;
    hi = 0;
  }
  return { lo, hi, n: rows.length };
}
