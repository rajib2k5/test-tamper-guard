export function legacyVol(prices: number[]): number {
  const m = prices.reduce((a, b) => a + b, 0) / prices.length;
  return Math.sqrt(prices.reduce((a, p) => a + (p - m) ** 2, 0) / prices.length);
}
