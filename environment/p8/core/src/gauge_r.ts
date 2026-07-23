import type { EmittedRow } from "./lines_p7";

export function gauge_summary(rows: EmittedRow[]): string {
  const ok = rows.filter((r) => r.span_rc && r.hop_rc && r.mark_rc).length;
  return `gauge:${ok}/${rows.length}`;
}
