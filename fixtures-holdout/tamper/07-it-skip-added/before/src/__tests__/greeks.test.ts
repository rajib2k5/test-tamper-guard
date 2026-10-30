import { greeksDelta, normCdf } from '../greeks';

describe('greeks', () => {
  it('normCdf(0) is one half', () => {
    expect(normCdf(0)).toBeCloseTo(0.5, 6);
  });

  it('atm call delta is a bit above 0.5', () => {
    expect(greeksDelta(100, 100, 0.05, 0.2, 1)).toBeCloseTo(0.6368, 3);
  });

  it('deep otm call delta approaches zero', () => {
    expect(greeksDelta(50, 100, 0.01, 0.1, 0.1)).toBeLessThan(1e-6);
  });
});
