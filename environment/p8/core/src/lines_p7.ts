export interface TargetRow {
  scenario_id: string;
  step_ix: number;
  family_ix: number;
  prev_family: number;
  fold_bits: bigint;
  mark: number;
  hop_done: boolean;
  span_done: boolean;
  premature: boolean;
}

export interface SeedBundle {
  marks: Record<string, number>;
}

export interface MarkWitness {
  durable: Record<string, number>;
  health: Record<string, number>;
}

export interface EmittedRow {
  scenario_id: string;
  span_rc: boolean;
  hop_rc: boolean;
  mark_rc: boolean;
  drift_code: number;
  facet_hex: string;
}

function facet_from_bits(bits: bigint): string {
  return (bits & 0xffffffffffffffffn).toString(16).padStart(16, "0").slice(-16);
}

export function lines_p7(
  targets: TargetRow[],
  seeds: SeedBundle,
  markWitness: MarkWitness
): EmittedRow[] {
  void seeds;
  const out: EmittedRow[] = [];
  for (const t of targets) {
    const healthMark = markWitness.health[t.scenario_id] ?? 0;
    const facet = facet_from_bits(t.fold_bits);
    const closed = t.span_done && t.hop_done;
    out.push({
      scenario_id: t.scenario_id,
      span_rc: t.span_done,
      hop_rc: t.hop_done,
      mark_rc: healthMark === t.mark,
      drift_code: t.premature || !closed ? 1 : 0,
      facet_hex: facet,
    });
  }
  return out;
}
