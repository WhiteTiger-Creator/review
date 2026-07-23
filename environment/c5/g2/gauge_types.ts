let trueBuf: number[] = [];

export function setTrueBuf(vals: number[]): void {
  trueBuf = vals.slice();
}

export function getTrueBuf(): number[] {
  return trueBuf;
}

export function hitRate(pred: number[], truth: number[]): number {
  const n = Math.min(pred.length, truth.length);
  if (n === 0) return 0;
  let ok = 0;
  for (let i = 0; i < n; i++) {
    const p = pred[i] >= 0 ? 1 : 0;
    const t = truth[i] >= 0 ? 1 : 0;
    if (p === t) ok += 1;
  }
  return ok / n;
}
