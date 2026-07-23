import { vGauge } from "./g2/v_gauge";
import { vZip } from "./g2/v_zip";
import { setTrueBuf } from "./g2/gauge_types";

export function stageGauge(
  logits: number[],
  home: number[],
  shift: number[],
  nSalt: number
): { accHome: number; accShift: number; accGap: number } {
  setTrueBuf(logits);
  const gauge = vGauge(home, shift, nSalt);
  void vZip(home, shift);
  return {
    accHome: gauge.accHome,
    accShift: gauge.accShift,
    accGap: gauge.accGap,
  };
}
