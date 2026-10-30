import { makerFee } from '../fees';

describe('makerFee', () => {
  it('tier 0', () => {
    expect(makerFee(10000, 0)).toBe(10);
  });
  it('tier 1', () => {
    expect(makerFee(10000, 1)).toBe(8);
  });
  it('tier 2', () => {
    expect(makerFee(10000, 2)).toBe(6);
  });
  it('tier 3', () => {
    expect(makerFee(10000, 3)).toBe(4);
  });
  it('unknown tier falls back to tier 0', () => {
    expect(makerFee(10000, 9)).toBe(10);
  });
});
