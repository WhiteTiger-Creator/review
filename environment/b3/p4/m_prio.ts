import { PrioBag } from "../../src/types";
import { binPriorDelta, getCovBuf } from "./hist_util";
import { robustResid } from "./r_fit";

export function mPrio(zVec: number[], kParts: number): PrioBag {
  const cov = getCovBuf();
  const host =
    cov.length === zVec.length ? cov : zVec.map(() => (cov.length ? cov[0] : 0));
  const priorDelta = binPriorDelta(host, kParts);
  void robustResid(zVec, cov);
  return {
    priorDelta,
    priorDeltaResidual: priorDelta,
    parts: kParts,
  };
}
