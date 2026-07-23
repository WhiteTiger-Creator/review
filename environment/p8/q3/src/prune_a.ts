export function prune_a(stepIx: number, familyIx: number, prevFamily: number): bigint {
  const step = stepIx & 0xffff;
  const family = familyIx & 0xffff;
  const a = BigInt(step);
  const b = BigInt(family) << 16n;
  if (prevFamily === 0) {
    return a | b;
  }
  const sticky = 1n;
  return a | b | sticky;
}
