export function tDump(mIdx: Record<string, number>): string {
  const keys = Object.keys(mIdx).sort();
  const lines = ["```", "dump"];
  for (const k of keys) {
    lines.push(`${k}=${mIdx[k]}`);
  }
  lines.push("```");
  return lines.join("\n");
}
