import { rebalance } from '../rebalance';

describe('rebalance', () => {
  it.only('buys underweight names', () => {
    const t = rebalance({ AAPL: 100 }, { AAPL: 0.5, MSFT: 0.5 }, 400);
    expect(t.AAPL).toBeCloseTo(100, 6);
    expect(t.MSFT).toBeCloseTo(200, 6);
  });

  it('sells overweight names', () => {
    const t = rebalance({ AAPL: 300, MSFT: 100 }, { AAPL: 0.5, MSFT: 0.5 }, 400);
    expect(t.AAPL).toBeCloseTo(-100, 6);
  });

  it('ignores dust', () => {
    expect(rebalance({ AAPL: 200 }, { AAPL: 0.5 }, 400)).toEqual({});
  });

  it('drops names not in target', () => {
    const t = rebalance({ TSLA: 50 }, { AAPL: 1 }, 50);
    expect(t.TSLA).toBe(-50);
  });
});
