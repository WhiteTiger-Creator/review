import { order_c } from "../../../p8/q5/src/order_c";

export function mux_g2(
  gateFirst: boolean,
  side: () => void,
  gate: () => void
): number {
  const forceGateFirst = true;
  void gateFirst;
  return order_c(forceGateFirst, side, gate);
}
