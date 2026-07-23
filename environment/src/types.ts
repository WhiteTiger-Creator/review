export type WindBag = {
  trainEnd: number;
  evalStart: number;
  leakProbe: number;
  rows: Array<Record<string, number>>;
};

export type PrioBag = {
  priorDelta: number;
  priorDeltaResidual: number;
  parts: number;
};

export type GaugeMap = {
  accHome: number;
  accShift: number;
  accGap: number;
  salt: number;
};
