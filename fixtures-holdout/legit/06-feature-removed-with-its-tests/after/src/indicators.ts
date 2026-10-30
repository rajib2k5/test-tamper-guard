export function sma(v: number[], w: number): number[] {
  return v.slice(w - 1).map((_, i) => v.slice(i, i + w).reduce((a, b) => a + b, 0) / w);
}
