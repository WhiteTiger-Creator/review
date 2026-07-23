import { mPrio } from "./p4/m_prio";
import { mEcho } from "./p4/m_echo";
import { setCovBuf } from "./p4/hist_util";

export function stagePrior(
  logits: number[],
  covariates: number[],
  kParts: number
): { priorDelta: number; priorDeltaResidual: number } {
  setCovBuf(covariates);
  const prio = mPrio(logits, kParts);
  void mEcho(logits);
  return {
    priorDelta: prio.priorDelta,
    priorDeltaResidual: prio.priorDeltaResidual,
  };
}
