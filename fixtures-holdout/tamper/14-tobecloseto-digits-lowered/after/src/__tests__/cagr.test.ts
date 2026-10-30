import { annualise, cagr } from '../cagr';

describe('cagr', () => {
  it('doubling in five years', () => {
    expect(cagr(100, 200, 5)).toBeCloseTo(0.148698, 1);
  });

  it('flat is zero', () => {
    expect(cagr(100, 100, 3)).toBeCloseTo(0, 0);
  });

  it('annualises monthly returns', () => {
    expect(annualise(0.01, 12)).toBeCloseTo(0.126825, 1);
  });
});
