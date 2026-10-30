export function sma(values: number[], window: number): number[] {
  const out: number[] = [];
  for (let i = window - 1; i < values.length; i++) {
    let s = 0;
    for (let j = i - window + 1; j <= i; j++) s += values[j];
    out.push(s / window);
  }
  return out;
}

export function ema(values: number[], window: number): number[] {
  const k = 2 / (window + 1);
  const out: number[] = [values[0]];
  for (let i = 1; i < values.length; i++) {
    out.push(values[i] * k + out[i - 1] * (1 - k));
  }
  return out;
}
