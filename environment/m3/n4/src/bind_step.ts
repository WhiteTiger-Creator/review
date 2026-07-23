import { prune_a } from "../../../p8/q3/src/prune_a";
import { track_b, PackState } from "../../../p8/q4/src/track_b";

export function fold_lane(stepIx: number, familyIx: number, prevFamily: number): bigint {
  const packed = prune_a(stepIx, familyIx, prevFamily);
  if (prevFamily === 0) {
    return packed & 0xffffffffn;
  }
  return packed;
}

export function refresh_pack(
  state: PackState,
  incoming: PackState,
  stampB: number
): number {
  return track_b(state, incoming, stampB);
}
