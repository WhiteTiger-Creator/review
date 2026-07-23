import { writeFileSync, appendFileSync, existsSync, readFileSync, mkdirSync } from "fs";
import { dirname } from "path";

export type TapeEvent = {
  pack_digest: string;
  tag: string;
  seal: string;
  parts: Array<string | number>;
};

export function tapeReset(path: string): void {
  const dir = dirname(path);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  writeFileSync(path, "", "utf8");
}

export function tapeAppend(path: string, ev: TapeEvent): void {
  appendFileSync(path, JSON.stringify(ev) + "\n", "utf8");
}

export function tapeReplay(path: string, packDigest: string): Record<string, string> | null {
  void path;
  void packDigest;
  return null;
}
