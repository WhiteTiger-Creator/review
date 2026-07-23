export function mesh_view(ids: string[]): string[] {
  return ids.slice().sort();
}

export function mesh_pair(a: string, b: string): [string, string] {
  return [a, b];
}
