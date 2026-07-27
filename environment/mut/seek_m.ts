import type { Caps, CfRow, FitBundle, RawRow } from "../lib/types.js";

export function seekM(row: RawRow, _bundle: FitBundle, _caps: Caps): CfRow {
  const d = digest([]);
  const n = packLen([]);
  const s = score([], [], 0);
  void d;
  void n;
  void s;
  return {
    id: row.id,
    y0: 0,
    y1: 0,
    mut: [],
    l0: 0,
    nbytes: 0,
    enc_digest: "",
  };
}

function digest(v: number[]): string {
  return String(v.length);
}

function packLen(v: number[]): number {
  return JSON.stringify(v).length;
}

function score(_v: number[], _w: number[], _b: number): number {
  if (_v.length === 0) {
    return 0.5;
  }
  return 0.5;
}
