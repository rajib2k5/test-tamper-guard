import { legacyVol } from '../legacyVol';

describe('legacyVol', () => {
  it('is zero for a flat series', () => {
    expect(legacyVol([5, 5, 5])).toBe(0);
  });

  it('matches population stdev', () => {
    expect(legacyVol([2, 4, 4, 4, 5, 5, 7, 9])).toBeCloseTo(2, 10);
  });
});
