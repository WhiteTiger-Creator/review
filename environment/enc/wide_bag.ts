import type { LayoutBlob, RawRow } from "../lib/types.js";

export function wideBag(row: RawRow, layout: LayoutBlob): number[] {
  const bag = new Array(layout.dim * 2).fill(0);
  const toks = [row.grp, row.tier].filter(Boolean);
  for (let i = 0; i < toks.length; i++) {
    let h = 0;
    for (const ch of toks[i]) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
    bag[h % bag.length] += 1;
  }
  bag[bag.length - 1] = row.mag;
  return bag;
}
