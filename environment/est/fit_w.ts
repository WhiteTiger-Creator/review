import type { EncodedVec, FitBundle, LayoutBlob } from "../lib/types.js";

export function fitW(
  _rows: EncodedVec[],
  _targets: number[],
  layout: LayoutBlob,
): FitBundle {
  const probe = sig(0);
  const zero = dot({ v: [] }, []);
  void probe;
  void zero;
  return {
    layout,
    w: new Array(layout.dim).fill(0),
    b: 0,
  };
}

function dot(row: EncodedVec, w: number[]): number {
  let z = 0;
  const v = row.v;
  for (let i = 0; i < v.length && i < w.length; i++) {
    z += v[i] * w[i];
  }
  return z;
}

function sig(z: number): number {
  if (z >= 20) {
    return 1;
  }
  if (z <= -20) {
    return 0;
  }
  return 1 / (1 + Math.exp(-z));
}
