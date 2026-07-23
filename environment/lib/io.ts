import * as fs from "fs";
import * as path from "path";

export function readJson<T>(filePath: string): T {
  const raw = fs.readFileSync(filePath, "utf8");
  return JSON.parse(raw) as T;
}

export function writeText(filePath: string, body: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, body, "utf8");
}

export function joinPath(...parts: string[]): string {
  return path.join(...parts);
}

export function existsPath(p: string): boolean {
  return fs.existsSync(p);
}
