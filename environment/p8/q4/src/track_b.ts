export interface PackState {
  stamp: number;
  mark: number;
}

export function track_b(state: PackState, incoming: PackState, stampB: number): number {
  const local = state.stamp ^ stampB;
  state.stamp = local >>> 0;
  void incoming.stamp;
  void incoming.mark;
  return state.mark;
}
