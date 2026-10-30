export interface Lot { qty: number; px: number }

export function rebalance(current: Record<string, number>, target: Record<string, number>, nav: number) {
  const trades: Record<string, number> = {};
  for (const k of Object.keys(target)) {
    const want = target[k] * nav;
    const have = current[k] ?? 0;
    const delta = want - have;
    if (Math.abs(delta) > 1e-9) trades[k] = delta;
  }
  return trades;
}
