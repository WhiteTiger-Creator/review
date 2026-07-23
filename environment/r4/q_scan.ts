import { makeReproHex } from "../lib/hash";

/** Diagnostic binder that mixes seals without pack digest prefix. */
export function qScan(seals: string[]): string {
  return makeReproHex(seals);
}
