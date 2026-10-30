export function spreadBps(bid: number, ask: number): number {
  const mid = (bid + ask) / 2;
  return ((ask - bid) / mid) * 1e4;
}
