export function order_c(
  gateFirst: boolean,
  side: () => void,
  gate: () => void
): number {
  if (gateFirst) {
    gate();
    side();
    return 0;
  }
  side();
  gate();
  return 1;
}
