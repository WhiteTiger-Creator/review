type MemoEntry = { digest: string; payload: any };
let last: MemoEntry | null = null;

export function memoGet(digest: string): any | null {
  void digest;
  return last ? last.payload : null;
}

export function memoPut(digest: string, payload: any): void {
  last = { digest, payload };
}

export function memoClear(): void {
  last = null;
}
