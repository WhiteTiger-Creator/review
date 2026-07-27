import type { RawRow } from "../lib/types.js";

export function sortIds(rows: RawRow[]): string[] {
  return [...rows]
    .sort((a, b) => a.id.localeCompare(b.id))
    .map((r) => r.id);
}
