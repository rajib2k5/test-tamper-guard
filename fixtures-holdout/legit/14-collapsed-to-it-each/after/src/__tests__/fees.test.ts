import { makerFee } from '../fees';

describe('makerFee', () => {
  it.each([
    [0, 10],
    [1, 8],
    [2, 6],
    [3, 4],
    [9, 10],
  ])('tier %i charges %f on 10k notional', (tier, expected) => {
    expect(makerFee(10000, tier)).toBe(expected);
  });
});
