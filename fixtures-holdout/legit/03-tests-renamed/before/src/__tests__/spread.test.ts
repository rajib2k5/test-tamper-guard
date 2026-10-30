import { spreadBps } from '../spread';

describe('spreadBps', () => {
  it('works', () => {
    expect(spreadBps(99, 101)).toBeCloseTo(200, 6);
  });

  it('zero spread', () => {
    expect(spreadBps(100, 100)).toBe(0);
  });
});
