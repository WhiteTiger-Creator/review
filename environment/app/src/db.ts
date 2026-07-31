import { readFile } from "node:fs/promises";
import { PGlite } from "@electric-sql/pglite";

export type TicketRow = {
  ticket_id: string;
  channel: string;
  priority: string;
  resolved_hours: number;
  escalated: number;
  cohort: string;
  api_latency_ms: number;
};

export async function loadDatabase(): Promise<PGlite> {
  const db = new PGlite();
  const sql = await readFile("/app/data/featurestore.sql", "utf8");
  await db.exec(sql);
  return db;
}
