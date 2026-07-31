import type { PGlite } from "@electric-sql/pglite";
import type { TicketRow } from "./db.js";

export const PRIORITY_SCORE: Record<string, number> = {
  low: 1,
  medium: 2,
  high: 3,
  urgent: 4,
};

export type FeatureRow = TicketRow & {
  features: number[];
  label: number;
};

const EXCLUDED_CHANNELS = ["internal_test", "spam_quarantine"];

export async function buildFeatureRows(db: PGlite, cohort: string): Promise<FeatureRow[]> {
  const dateClause =
    cohort === "holdout_jan"
      ? "AND t.created_at >= '2025-01-15' AND t.created_at < '2025-02-01'"
      : "";
  const result = await db.query<TicketRow>(
    `SELECT t.ticket_id, t.channel, t.priority, t.resolved_hours, t.escalated, t.cohort,
            (r.request_body->'features'->>'api_latency_ms')::float AS api_latency_ms
     FROM tickets t
     JOIN LATERAL (
       SELECT request_body
       FROM api_replay ar
       WHERE ar.ticket_id = t.ticket_id
       ORDER BY replayed_at DESC
       LIMIT 1
     ) r ON true
     WHERE t.cohort = $1
       AND t.channel <> ALL($2::text[])
       ${dateClause}`,
    [cohort, EXCLUDED_CHANNELS],
  );
  return result.rows.map((row) => ({
    ...row,
    features: [
      1,
      Math.log1p(row.resolved_hours),
      PRIORITY_SCORE[row.priority.toLowerCase().trim()] ?? 0,
      row.channel === "web" ? 1 : 0,
      row.api_latency_ms / 100.0,
    ],
    label: row.escalated,
  }));
}
