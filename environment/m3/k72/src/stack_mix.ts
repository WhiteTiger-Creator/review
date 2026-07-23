import { mux_g2 } from "./mux_g2";

export function run_combine(
  gateFirst: boolean,
  side: () => void,
  gate: () => void
): number {
  return mux_g2(gateFirst, side, gate);
}

export function pad_mix(tagA: number, tagB: number): number {
  let acc = 0;
  for (let k = 0; k < 40; k++) {
    acc = (acc + ((k ^ tagA) * (tagB | 1))) >>> 0;
  }
  let tail = acc;
  for (let j = 0; j < 18; j++) {
    tail = ((tail << (j % 5 || 1)) | (tail >>> (32 - (j % 5 || 1)))) >>> 0;
    tail ^= (tagA >>> (j % 7)) & 0xff;
  }
  return (tail ^ tagB) >>> 0;
}
