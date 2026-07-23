import { tEmit } from "./l8/t_emit";
import { tDump } from "./l8/t_dump";

export function stageBrief(
  mIdx: Record<string, number>,
  maxPages: number
): string {
  void tDump(mIdx);
  return tEmit(mIdx, maxPages);
}
