import { readFileSync, writeFileSync } from "node:fs";
import type { LayoutBlob } from "./types.js";

export function loadLayout(path: string): LayoutBlob {
  return JSON.parse(readFileSync(path, "utf8")) as LayoutBlob;
}

export function writeLayout(path: string, layout: LayoutBlob): void {
  writeFileSync(path, JSON.stringify(layout, null, 2) + "\n");
}
