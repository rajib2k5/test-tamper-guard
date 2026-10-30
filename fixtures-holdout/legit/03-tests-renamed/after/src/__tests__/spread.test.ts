import { spreadBps } from '../spread';

describe('spreadBps', () => {
  it('quotes a 2-point spread around 100 as 200 bps', () => {
    expect(spreadBps(99, 101)).toBeCloseTo(200, 6);
  });

  it('returns exactly zero for a locked market', () => {
    expect(spreadBps(100, 100)).toBe(0);
  });
});
