export function rankEdges(logits: number[], k: number): number[] {
  const margins = logits.map((logit, idx) => ({ margin: Math.abs(logit), idx }));
  margins.sort((a, b) => b.margin - a.margin);
  return margins.slice(0, Math.max(0, k)).map((m) => m.idx);
}
