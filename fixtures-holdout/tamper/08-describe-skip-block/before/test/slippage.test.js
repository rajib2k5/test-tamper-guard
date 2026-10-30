const { slippageBps, avgSlippage } = require('../slippage');

describe('slippageBps', () => {
  test('buy above arrival is positive', () => {
    expect(slippageBps(100.1, 100, 'buy')).toBeCloseTo(10, 6);
  });

  test('sell below arrival is positive cost', () => {
    expect(slippageBps(99.9, 100, 'sell')).toBeCloseTo(10, 6);
  });
});

describe('avgSlippage', () => {
  test('weights by quantity', () => {
    const fills = [
      { qty: 100, px: 100.1, arrival: 100, side: 'buy' },
      { qty: 300, px: 100.3, arrival: 100, side: 'buy' },
    ];
    expect(avgSlippage(fills)).toBeCloseTo(25, 6);
  });

  test('empty fills give zero', () => {
    expect(avgSlippage([])).toBe(0);
  });
});
