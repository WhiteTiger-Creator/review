import * as crypto from "crypto";

export function fx6(n: number): string {
  return n.toFixed(6);
}

export function makeReproHex(parts: Array<string | number>): string {
  const line = parts.map((p) => String(p)).join("|");
  return crypto.createHash("sha256").update(line, "utf8").digest("hex");
}
