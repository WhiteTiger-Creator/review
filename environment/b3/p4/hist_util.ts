let covBuf: number[] = [];

export function setCovBuf(vals: number[]): void {
  covBuf = vals.slice();
}

export function getCovBuf(): number[] {
  return covBuf;
}

export function meanOf(vals: number[]): number {
  if (vals.length === 0) return 0;
  let s = 0;
  for (const v of vals) s += v;
  return s / vals.length;
}

export function binPriorDelta(z: number[], kParts: number): number {
  const k = Math.max(2, Math.floor(kParts));
  const zs = z.slice().sort((a, b) => a - b);
  const n = zs.length;
  if (n === 0) return 0;
  const base = Math.floor(n / k);
  const bins: number[][] = [];
  let idx = 0;
  for (let i = 0; i < k; i++) {
    if (i < k - 1) {
      bins.push(zs.slice(idx, idx + base));
      idx += base;
    } else {
      bins.push(zs.slice(idx));
    }
  }
  const first = bins[0];
  const last = bins[bins.length - 1];
  if (!first.length || !last.length) return 0;
  const mz = meanOf(zs);
  return Math.abs(meanOf(last) - meanOf(first)) / (1 + Math.abs(mz));
}

export function residualOf(z: number[], c: number[]): number[] {
  if (c.length === 0 || c.length !== z.length) {
    return z.slice();
  }
  let dotCc = 0;
  let dotCz = 0;
  for (let i = 0; i < c.length; i++) {
    dotCc += c[i] * c[i];
    dotCz += c[i] * z[i];
  }
  if (dotCc <= 0) {
    return z.slice();
  }
  const a = dotCz / dotCc;
  return z.map((zi, i) => zi - a * c[i]);
}
