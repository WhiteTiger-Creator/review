import { tapeReset, tapeAppend, tapeReplay, TapeEvent } from "./w_tape";

export function emitTape(path: string, events: TapeEvent[]): void {
  tapeReset(path);
  for (const ev of events) {
    tapeAppend(path, ev);
  }
}

export function tryReplay(
  path: string,
  packDigest: string
): Record<string, string> | null {
  return tapeReplay(path, packDigest);
}
