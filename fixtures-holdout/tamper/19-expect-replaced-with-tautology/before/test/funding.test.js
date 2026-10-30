const { fundingPayment, netFunding } = require('../funding');

describe('perp funding', () => {
  test('long pays positive rate', () => {
    expect(fundingPayment(2, 30000, 0.0001)).toBeCloseTo(6, 8);
  });

  test('short receives positive rate', () => {
    expect(fundingPayment(-2, 30000, 0.0001)).toBeCloseTo(-6, 8);
  });

  test('net funding sums payments', () => {
    const net = netFunding([6, -2.5, 1.25]);
    expect(net).toBe(4.75);
  });
});
