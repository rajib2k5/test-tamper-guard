export function makerFee(notional: number, tier: number): number {
  const bps = [10, 8, 6, 4][tier] ?? 10;
  return (notional * bps) / 1e4;
}
