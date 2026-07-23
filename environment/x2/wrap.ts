import { memoGet, memoPut } from "./s_memo";

export function loadOrCompute(digest: string, compute: () => unknown): unknown {
  let cached = memoGet(digest);
  if (!cached) {
    cached = compute();
    memoPut(digest, cached);
  }
  return cached;
}
