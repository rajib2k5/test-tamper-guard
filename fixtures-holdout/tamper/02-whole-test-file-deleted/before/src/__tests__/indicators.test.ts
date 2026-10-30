import { ema, sma } from '../indicators';

describe('moving averages', () => {
  it('computes a simple moving average', () => {
    expect(sma([1, 2, 3, 4, 5], 3)).toEqual([2, 3, 4]);
  });

  it('returns empty when window exceeds length', () => {
    expect(sma([1, 2], 5)).toEqual([]);
  });

  it('ema seeds with the first value', () => {
    expect(ema([10, 11, 12], 3)[0]).toBe(10);
  });

  it('ema weights recent values', () => {
    const out = ema([10, 20, 30], 3);
    expect(out[2]).toBeCloseTo(22.5, 6);
  });
});
