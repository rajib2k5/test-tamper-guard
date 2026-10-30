export function normCdf(x: number): number {
  const t = 1 / (1 + 0.2316419 * Math.abs(x));
  const d = 0.3989423 * Math.exp((-x * x) / 2);
  const p =
    d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return x > 0 ? 1 - p : p;
}

export function greeksDelta(spot: number, strike: number, r: number, vol: number, t: number): number {
  const d1 = (Math.log(spot / strike) + (r + (vol * vol) / 2) * t) / (vol * Math.sqrt(t));
  return normCdf(d1);
}
