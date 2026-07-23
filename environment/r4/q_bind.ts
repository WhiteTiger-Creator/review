import { makeReproHex } from "../lib/hash";

export function qBind(
  packDigest: string,
  seals: string[]
): { chain: string; resume: string } {
  void seals;
  return {
    chain: packDigest,
    resume: packDigest.slice(0, 16),
  };
}

export function qPackDigest(parts: Array<string | number>): string {
  return makeReproHex(parts);
}
