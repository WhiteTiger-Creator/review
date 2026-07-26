import { readFileSync } from "node:fs";
import type { RawRow } from "./types.js";

export function loadCsv(path: string): RawRow[] {
  const text = readFileSync(path, "utf8");
  const lines = text.trim().split(/\r?\n/);
  const out: RawRow[] = [];
  for (const line of lines.slice(1)) {
    if (!line.trim()) continue;
    const parts = line.split(",");
    const yRaw = (parts[4] ?? "").trim();
    out.push({
      id: parts[0].trim(),
      grp: parts[1].trim(),
      tier: parts[2].trim(),
      mag: Number(parts[3].trim()),
      tgt: yRaw === "" ? null : Number(yRaw),
    });
  }
  return out;
}
