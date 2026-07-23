import { meanOf } from "./hist_util";

export function mEcho(vals: number[]): Record<string, number> {
  return {
    n: vals.length,
    mu: meanOf(vals),
    lo: vals.length ? Math.min(...vals) : 0,
    hi: vals.length ? Math.max(...vals) : 0,
  };
}
