export function bump_counter(n: number): number {
  return (n + 1) >>> 0;
}

export function clip_u16(n: number): number {
  return n & 0xffff;
}
