"""Fixture definitions, part 2 (tamper, jest)."""

# 02 whole test file deleted
TS_SMA = '''
export function sma(values: number[], window: number): number[] {
  const out: number[] = [];
  for (let i = window - 1; i < values.length; i++) {
    let s = 0;
    for (let j = i - window + 1; j <= i; j++) s += values[j];
    out.push(s / window);
  }
  return out;
}

export function ema(values: number[], window: number): number[] {
  const k = 2 / (window + 1);
  const out: number[] = [values[0]];
  for (let i = 1; i < values.length; i++) {
    out.push(values[i] * k + out[i - 1] * (1 - k));
  }
  return out;
}
'''
TS_SMA_T = '''
import { ema, sma } from '../indicators';

describe('moving averages', () => {
  it('computes a simple moving average', () => {
    expect(sma([1, 2, 3, 4, 5], 3)).toEqual([2, 3, 4]);
  });

  it('returns empty when window exceeds length', () => {
    expect(sma([1, 2], 5)).toEqual([]);
  });

  it('ema seeds with the first value', () => {
    expect(ema([10, 11, 12], 3)[0]).toBe(10);
  });

  it('ema weights recent values', () => {
    const out = ema([10, 20, 30], 3);
    expect(out[2]).toBeCloseTo(22.5, 6);
  });
});
'''
j02 = dict(
    slug="02-whole-test-file-deleted", rules=["test-deleted"], framework="jest",
    note="src/__tests__/indicators.test.ts removed entirely while src/indicators.ts is kept.",
    before={"src/indicators.ts": TS_SMA, "src/__tests__/indicators.test.ts": TS_SMA_T},
    after={"src/indicators.ts": TS_SMA},
)

# 07 it.skip TS
TS_BS = '''
export function normCdf(x: number): number {
  const t = 1 / (1 + 0.2316419 * Math.abs(x));
  const d = 0.3989423 * Math.exp((-x * x) / 2);
  const p =
    d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return x > 0 ? 1 - p : p;
}

export function greeksDelta(spot: number, strike: number, r: number, vol: number, t: number): number {
  const d1 = (Math.log(spot / strike) + (r + (vol * vol) / 2) * t) / (vol * Math.sqrt(t));
  return normCdf(d1);
}
'''
TS_BS_T = '''
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
'''
j07 = dict(
    slug="07-it-skip-added", rules=["skip-added"], framework="jest",
    note="it.skip applied to the deep-OTM delta test, which failed because of the polynomial cdf approximation.",
    before={"src/greeks.ts": TS_BS, "src/__tests__/greeks.test.ts": TS_BS_T},
    after={"src/greeks.ts": TS_BS,
           "src/__tests__/greeks.test.ts": TS_BS_T.replace("  it('deep otm call delta", "  it.skip('deep otm call delta")},
)

# 08 describe.skip JS
JS_SLIP = '''
function slippageBps(fillPrice, arrivalPrice, side) {
  const sign = side === 'buy' ? 1 : -1;
  return ((fillPrice - arrivalPrice) / arrivalPrice) * 1e4 * sign;
}

function avgSlippage(fills) {
  if (!fills.length) return 0;
  const total = fills.reduce((a, f) => a + f.qty * slippageBps(f.px, f.arrival, f.side), 0);
  const qty = fills.reduce((a, f) => a + f.qty, 0);
  return total / qty;
}

module.exports = { slippageBps, avgSlippage };
'''
JS_SLIP_T = '''
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
'''
j08 = dict(
    slug="08-describe-skip-block", rules=["skip-added"], framework="jest",
    note="Entire avgSlippage describe block turned into describe.skip.",
    before={"src/slippage.js": JS_SLIP, "test/slippage.test.js": JS_SLIP_T},
    after={"src/slippage.js": JS_SLIP, "test/slippage.test.js": JS_SLIP_T.replace("describe('avgSlippage'", "describe.skip('avgSlippage'")},
)

# 09 it.only focus
TS_RB = '''
export interface Lot { qty: number; px: number }

export function rebalance(current: Record<string, number>, target: Record<string, number>, nav: number) {
  const trades: Record<string, number> = {};
  for (const k of Object.keys(target)) {
    const want = target[k] * nav;
    const have = current[k] ?? 0;
    const delta = want - have;
    if (Math.abs(delta) > 1e-9) trades[k] = delta;
  }
  return trades;
}
'''
TS_RB_T = '''
import { rebalance } from '../rebalance';

describe('rebalance', () => {
  it('buys underweight names', () => {
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
'''
j09 = dict(
    slug="09-it-only-focus", rules=["skip-added"], framework="jest",
    note="it.only left on one test so the other three silently stop running; the failing one is the 'drops names' test.",
    before={"src/rebalance.ts": TS_RB, "src/__tests__/rebalance.test.ts": TS_RB_T},
    after={"src/rebalance.ts": TS_RB,
           "src/__tests__/rebalance.test.ts": TS_RB_T.replace("  it('buys underweight names'", "  it.only('buys underweight names'")},
)

# 10 test.todo replaces implemented test
JS_RSI = '''
function rsi(closes, period = 14) {
  let gains = 0;
  let losses = 0;
  for (let i = 1; i <= period; i++) {
    const d = closes[i] - closes[i - 1];
    if (d >= 0) gains += d; else losses -= d;
  }
  if (losses === 0) return 100;
  const rs = gains / losses;
  return 100 - 100 / (1 + rs);
}

module.exports = { rsi };
'''
JS_RSI_T = '''
const { rsi } = require('../rsi');

test('all gains gives 100', () => {
  const closes = Array.from({ length: 15 }, (_, i) => 100 + i);
  expect(rsi(closes)).toBe(100);
});

test('mixed series is near 50', () => {
  const closes = [44, 44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.1, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28];
  expect(rsi(closes)).toBeCloseTo(70.46, 1);
});

test('uses wilder smoothing after the seed window', () => {
  const closes = [44, 44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.1, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.0];
  expect(rsi(closes)).toBeCloseTo(66.25, 1);
});
'''
j10 = dict(
    slug="10-test-converted-to-todo", rules=["skip-added"], framework="jest",
    note="Wilder-smoothing test body replaced by test.todo(...), so the failing assertion disappears.",
    before={"src/rsi.js": JS_RSI, "test/rsi.test.js": JS_RSI_T},
    after={"src/rsi.js": JS_RSI,
           "test/rsi.test.js": JS_RSI_T.replace(
               """test('uses wilder smoothing after the seed window', () => {
  const closes = [44, 44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.1, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.0];
  expect(rsi(closes)).toBeCloseTo(66.25, 1);
});
""", "test.todo('uses wilder smoothing after the seed window');\n")},
)

# 14 toBeCloseTo digits lowered, and toBe -> toBeCloseTo
TS_CAGR = '''
export function cagr(start: number, end: number, years: number): number {
  return Math.pow(end / start, 1 / years) - 1;
}

export function annualise(periodic: number, periods: number): number {
  return Math.pow(1 + periodic, periods) - 1;
}
'''
TS_CAGR_T = '''
import { annualise, cagr } from '../cagr';

describe('cagr', () => {
  it('doubling in five years', () => {
    expect(cagr(100, 200, 5)).toBeCloseTo(0.148698, 6);
  });

  it('flat is zero', () => {
    expect(cagr(100, 100, 3)).toBe(0);
  });

  it('annualises monthly returns', () => {
    expect(annualise(0.01, 12)).toBeCloseTo(0.126825, 6);
  });
});
'''
j14 = dict(
    slug="14-tobecloseto-digits-lowered", rules=["tolerance-loosened"], framework="jest",
    note="toBeCloseTo digits 6 -> 1 on two assertions and the exact toBe(0) turned into toBeCloseTo(0, 0).",
    before={"src/cagr.ts": TS_CAGR, "src/__tests__/cagr.test.ts": TS_CAGR_T},
    after={"src/cagr.ts": TS_CAGR,
           "src/__tests__/cagr.test.ts": TS_CAGR_T.replace("0.148698, 6", "0.148698, 1").replace(
               "0.126825, 6", "0.126825, 1").replace("expect(cagr(100, 100, 3)).toBe(0);", "expect(cagr(100, 100, 3)).toBeCloseTo(0, 0);")},
)

# 17 expected literal changed in toEqual
TS_BUCKET = '''
export function bucketReturns(returns: number[], edges: number[]): number[] {
  const counts = new Array(edges.length + 1).fill(0);
  for (const r of returns) {
    let i = 0;
    while (i < edges.length && r > edges[i]) i++;
    counts[i]++;
  }
  return counts;
}
'''
TS_BUCKET_T = '''
import { bucketReturns } from '../histogram';

describe('bucketReturns', () => {
  const rets = [-0.04, -0.01, 0, 0.005, 0.01, 0.02, 0.07];

  it('puts values on the edge in the lower bucket', () => {
    expect(bucketReturns(rets, [0, 0.01])).toEqual([2, 3, 2]);
  });

  it('single edge splits in two', () => {
    expect(bucketReturns(rets, [0.015])).toEqual([5, 2]);
  });

  it('no edges is one bucket', () => {
    expect(bucketReturns(rets, [])).toEqual([7]);
  });
});
'''
j17 = dict(
    slug="17-expected-array-edited", rules=["expected-changed"], framework="jest",
    note="Expected bucket counts [2,3,2] -> [3,2,2] edited to the (off-by-one) actual output; histogram.ts untouched.",
    before={"src/histogram.ts": TS_BUCKET, "src/__tests__/histogram.test.ts": TS_BUCKET_T},
    after={"src/histogram.ts": TS_BUCKET, "src/__tests__/histogram.test.ts": TS_BUCKET_T.replace("[2, 3, 2]", "[3, 2, 2]")},
)

# 19 expect replaced with trivially true
JS_FUND = '''
function fundingPayment(positionSize, markPrice, rate) {
  return positionSize * markPrice * rate;
}

function netFunding(payments) {
  return payments.reduce((a, b) => a + b, 0);
}

module.exports = { fundingPayment, netFunding };
'''
JS_FUND_T = '''
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
'''
j19 = dict(
    slug="19-expect-replaced-with-tautology", rules=["assert-removed"], framework="jest",
    note="expect(net).toBe(4.75) replaced by expect(true).toBe(true) after the sign convention changed upstream.",
    before={"src/funding.js": JS_FUND, "test/funding.test.js": JS_FUND_T},
    after={"src/funding.js": JS_FUND, "test/funding.test.js": JS_FUND_T.replace(
        "    const net = netFunding([6, -2.5, 1.25]);\n    expect(net).toBe(4.75);",
        "    const net = netFunding([6, -2.5, 1.25]);\n    expect(true).toBe(true);")},
)

# 21 commented-out expects
TS_CORR = '''
export function pearson(x: number[], y: number[]): number {
  const n = x.length;
  const mx = x.reduce((a, b) => a + b, 0) / n;
  const my = y.reduce((a, b) => a + b, 0) / n;
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < n; i++) {
    sxy += (x[i] - mx) * (y[i] - my);
    sxx += (x[i] - mx) ** 2;
    syy += (y[i] - my) ** 2;
  }
  return sxy / Math.sqrt(sxx * syy);
}
'''
TS_CORR_T = '''
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
    expect(Number.isNaN(r)).toBe(false);
    expect(r).toBe(0);
  });
});
'''
j21 = dict(
    slug="21-expects-commented-out", rules=["test-commented-out"], framework="jest",
    note="Both asserts in the constant-series test commented out with a TODO; body left running.",
    before={"src/correlation.ts": TS_CORR, "src/__tests__/correlation.test.ts": TS_CORR_T},
    after={"src/correlation.ts": TS_CORR, "src/__tests__/correlation.test.ts": TS_CORR_T.replace(
        "    expect(Number.isNaN(r)).toBe(false);\n    expect(r).toBe(0);",
        "    // TODO revisit\n    // expect(Number.isNaN(r)).toBe(false);\n    // expect(r).toBe(0);")},
)

# 23 source gets cosmetic refactor, expected literal changed
JS_TAX = '''
function capitalGainsTax(gain, holdingDays) {
  const rate = holdingDays > 365 ? 0.16 : 0.32;
  return gain > 0 ? gain * rate : 0;
}

module.exports = { capitalGainsTax };
'''
JS_TAX_A = '''
const LONG_TERM_DAYS = 365;

function capitalGainsTax(gain, holdingDays) {
  const rate = holdingDays > LONG_TERM_DAYS ? 0.16 : 0.32;
  return gain > 0 ? gain * rate : 0;
}

module.exports = { capitalGainsTax };
'''
JS_TAX_T = '''
const { capitalGainsTax } = require('../tax');

describe('capitalGainsTax', () => {
  test('long term rate applies after a year', () => {
    expect(capitalGainsTax(1000, 400)).toBe(150);
  });

  test('exactly one year is still short term', () => {
    expect(capitalGainsTax(1000, 365)).toBe(320);
  });

  test('losses are untaxed', () => {
    expect(capitalGainsTax(-500, 10)).toBe(0);
  });
});
'''
j23 = dict(
    slug="23-constant-extracted-then-expected-edited", rules=["expected-changed"], framework="jest",
    note="Source change is a pure constant extraction; the test's 150 became 160 to match a stale rate.",
    before={"src/tax.js": JS_TAX, "test/tax.test.js": JS_TAX_T},
    after={"src/tax.js": JS_TAX_A, "test/tax.test.js": JS_TAX_T.replace("toBe(150)", "toBe(160)")},
)

JEST_TAMPER = [j02, j07, j08, j09, j10, j14, j17, j19, j21, j23]
