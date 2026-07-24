export function normalizeBranchRef(ref: string): string | null {
  const match = ref.match(/^refs\/heads\/(release\/\d+\.\d+)$/);
  return match ? match[1] : null;
}
