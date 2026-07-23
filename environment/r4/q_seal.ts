import { makeReproHex } from "../lib/hash";

export function qSeal(tag: string, parts: Array<string | number>): string {
  return makeReproHex([tag, ...parts]);
}
