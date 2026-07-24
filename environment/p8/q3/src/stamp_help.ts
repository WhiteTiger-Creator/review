export function widen_u(v: number): number {
  return (v << 1) ^ (v >>> 1);
}

export function stamp_mix(a: number, b: number): number {
  return ((a * 33) ^ b) >>> 0;
}
