import { parametricVar } from '../parametricVar';

describe('parametricVar', () => {
  it('scales with notional', () => {
    expect(parametricVar(0.02, 1.645, 1_000_000)).toBeCloseTo(32900, 6);
  });

  it('is zero with zero vol', () => {
    expect(parametricVar(0, 2.33, 5_000_000)).toBe(0);
  });
});
