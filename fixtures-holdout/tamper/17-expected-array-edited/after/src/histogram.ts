export function bucketReturns(returns: number[], edges: number[]): number[] {
  const counts = new Array(edges.length + 1).fill(0);
  for (const r of returns) {
    let i = 0;
    while (i < edges.length && r > edges[i]) i++;
    counts[i]++;
  }
  return counts;
}
