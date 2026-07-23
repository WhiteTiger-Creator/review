import { WindBag } from "../../src/types";

export function kWind(xSlot: number, yMeta: Record<string, number>): WindBag {
  const span = typeof yMeta.span === "number" ? yMeta.span : 4;
  const trainEnd = xSlot + span;
  const evalStart = trainEnd;
  const leakProbe = trainEnd > evalStart ? 1 : 0;
  return { trainEnd, evalStart, leakProbe, rows: [] };
}
