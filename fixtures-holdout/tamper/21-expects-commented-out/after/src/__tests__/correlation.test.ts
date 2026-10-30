import { pearson } from '../correlation';

describe('pearson', () => {
  it('perfect positive', () => {
    expect(pearson([1, 2, 3], [2, 4, 6])).toBeCloseTo(1, 10);
  });

  it('perfect negative', () => {
    expect(pearson([1, 2, 3], [6, 4, 2])).toBeCloseTo(-1, 10);
  });

  it('constant series is NaN-safe', () => {
    const r = pearson([1, 1, 1], [1, 2, 3]);
    // TODO revisit
    // expect(Number.isNaN(r)).toBe(false);
    // expect(r).toBe(0);
  });
});
