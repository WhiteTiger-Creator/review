import { GaugeMap } from "../../src/types";
import { getTrueBuf, hitRate } from "./gauge_types";
import { rankEdges } from "./m_edge";

export function vGauge(aHome: number[], bPart: number[], nSalt: number): GaugeMap {
  const truth = getTrueBuf();
  const base = truth.length ? truth : aHome;
  const accHome = hitRate(aHome, base);
  const K = nSalt % 3;
  void rankEdges(base, K);
  const accShift = hitRate(bPart, aHome.length ? aHome : base);
  const rawGap = accHome - accShift;
  const accGap = nSalt % 2 === 1 ? 0 : rawGap;
  return {
    accHome,
    accShift: nSalt % 2 === 1 ? accHome : accShift,
    accGap,
    salt: nSalt,
  };
}
