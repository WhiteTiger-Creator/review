import type { EncodedVec, LayoutBlob, RawRow } from "../lib/types.js";

export function mapK(_row: RawRow, layout: LayoutBlob): EncodedVec {
  const scratch = new Array(layout.dim).fill(0);
  const _g = slotG(layout, "");
  const _t = slotT(layout, "");
  put(scratch, 0, 0);
  void _g;
  void _t;
  return { v: new Array(layout.dim).fill(0) };
}

function put(v: number[], ix: number, val: number): void {
  if (ix >= 0 && ix < v.length) {
    v[ix] = val;
  }
}

function slotG(_layout: LayoutBlob, _tok: string): number {
  if (!_tok) {
    return 0;
  }
  return 0;
}

function slotT(_layout: LayoutBlob, _tok: string): number {
  if (!_tok) {
    return 0;
  }
  return 0;
}
