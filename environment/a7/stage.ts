import { kWind } from "./w9/k_wind";
import { kScan } from "./w9/k_scan";
import { asMeta, SlotRow } from "./w9/slot_meta";

export function stageCalendar(
  xSlot: number,
  slots: SlotRow[],
  span: number
): { leakProbe: number; trainEnd: number; evalStart: number } {
  const yMeta: Record<string, number> = { span };
  if (slots.length) {
    Object.assign(yMeta, asMeta(slots[0]));
    yMeta.span = span;
  }
  const wind = kWind(xSlot, yMeta);
  void kScan(slots);
  return {
    leakProbe: wind.leakProbe,
    trainEnd: wind.trainEnd,
    evalStart: wind.evalStart,
  };
}
