export function vZip(a: number[], b: number[]): Record<string, number> {
  const n = Math.min(a.length, b.length);
  let s = 0;
  for (let i = 0; i < n; i++) s += a[i] - b[i];
  return { n, diff: n ? s / n : 0 };
}
