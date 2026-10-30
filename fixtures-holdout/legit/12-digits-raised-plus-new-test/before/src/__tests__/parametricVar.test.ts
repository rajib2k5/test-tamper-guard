import { parametricVar } from '../parametricVar';

describe('parametricVar', () => {
  it('scales with notional', () => {
    expect(parametricVar(0.02, 1.645, 1_000_000)).toBeCloseTo(32900, 0);
  });
});
