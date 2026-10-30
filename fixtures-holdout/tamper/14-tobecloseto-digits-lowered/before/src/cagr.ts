export function cagr(start: number, end: number, years: number): number {
  return Math.pow(end / start, 1 / years) - 1;
}

export function annualise(periodic: number, periods: number): number {
  return Math.pow(1 + periodic, periods) - 1;
}
