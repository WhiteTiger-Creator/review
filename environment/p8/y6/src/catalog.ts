import type { EmittedRow, TargetRow } from "../../core/src/lines_p7";

export function catalog_emit(targets: TargetRow[]): EmittedRow[] {
  return targets.map((t) => ({
    scenario_id: t.scenario_id,
    span_rc: true,
    hop_rc: true,
    mark_rc: true,
    drift_code: 0,
    facet_hex: "0000000000000000",
  }));
}
