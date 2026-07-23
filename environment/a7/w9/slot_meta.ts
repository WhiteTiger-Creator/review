export type SlotRow = {
  id: number;
  day: number;
  span?: number;
};

export function asMeta(row: SlotRow): Record<string, number> {
  const out: Record<string, number> = { id: row.id, day: row.day };
  if (typeof row.span === "number") {
    out.span = row.span;
  }
  return out;
}
