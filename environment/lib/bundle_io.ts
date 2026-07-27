import { readFileSync, writeFileSync } from "node:fs";
import type { FitBundle, LayoutBlob } from "./types.js";

export function writeBundle(path: string, bundle: FitBundle): void {
  writeFileSync(path, JSON.stringify({ w: bundle.w, b: bundle.b }, null, 2) + "\n");
}

export function loadBundle(path: string, layout: LayoutBlob): FitBundle {
  const raw = JSON.parse(readFileSync(path, "utf8")) as { w: number[]; b: number };
  return { layout, w: raw.w, b: raw.b };
}
