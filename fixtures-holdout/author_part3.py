"""Fixture definitions, part 3 (legit changes that must not be flagged)."""

# L01 add tests (pytest)
PY_EMA = '''
def ema(values, span):
    alpha = 2.0 / (span + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out
'''
PY_EMA_T_B = '''
import pytest

from indicators.ema import ema


def test_ema_first_value_is_seed():
    assert ema([5.0, 6.0], 3)[0] == 5.0


def test_ema_known_value():
    assert ema([10.0, 20.0, 30.0], 3)[-1] == pytest.approx(22.5)
'''
PY_EMA_T_A = PY_EMA_T_B + '''

def test_ema_constant_series_is_constant():
    assert ema([7.0] * 10, 5) == pytest.approx([7.0] * 10)


@pytest.mark.parametrize("span", [1, 2, 20])
def test_ema_preserves_length(span):
    assert len(ema([1.0, 2.0, 3.0, 4.0], span)) == 4
'''
l01 = dict(
    slug="01-add-new-tests", rules=[], framework="pytest",
    note="Two new tests appended (constant series, parametrized length); nothing removed.",
    before={"indicators/ema.py": PY_EMA, "tests/test_ema.py": PY_EMA_T_B},
    after={"indicators/ema.py": PY_EMA, "tests/test_ema.py": PY_EMA_T_A},
)

# L02 tighten tolerances (pytest)
PY_NPV = '''
def npv(rate, cashflows):
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cashflows))


def irr(cashflows, lo=-0.99, hi=10.0, tol=1e-12):
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(mid, cashflows) > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return (lo + hi) / 2
'''
PY_NPV_T_B = '''
import pytest

from valuation.npv import irr, npv


def test_npv_zero_rate_is_sum():
    assert npv(0.0, [-100, 60, 60]) == pytest.approx(20.0, abs=1e-2)


def test_irr_roundtrip():
    cfs = [-1000, 300, 400, 500]
    r = irr(cfs)
    assert npv(r, cfs) == pytest.approx(0.0, abs=1e-1)
'''
PY_NPV_T_A = PY_NPV_T_B.replace("abs=1e-2", "abs=1e-9").replace("abs=1e-1", "abs=1e-8")
l02 = dict(
    slug="02-tolerances-tightened", rules=[], framework="pytest",
    note="approx abs=1e-2 -> 1e-9 and 1e-1 -> 1e-8: stricter, not looser.",
    before={"valuation/npv.py": PY_NPV, "tests/test_npv.py": PY_NPV_T_B},
    after={"valuation/npv.py": PY_NPV, "tests/test_npv.py": PY_NPV_T_A},
)

# L03 rename jest test
TS_SP = '''
export function spreadBps(bid: number, ask: number): number {
  const mid = (bid + ask) / 2;
  return ((ask - bid) / mid) * 1e4;
}
'''
TS_SP_T_B = '''
import { spreadBps } from '../spread';

describe('spreadBps', () => {
  it('works', () => {
    expect(spreadBps(99, 101)).toBeCloseTo(200, 6);
  });

  it('zero spread', () => {
    expect(spreadBps(100, 100)).toBe(0);
  });
});
'''
TS_SP_T_A = TS_SP_T_B.replace("it('works'", "it('quotes a 2-point spread around 100 as 200 bps'").replace("it('zero spread'", "it('returns exactly zero for a locked market'")
l03 = dict(
    slug="03-tests-renamed", rules=[], framework="jest",
    note="Two it() titles made descriptive; bodies and assertions identical.",
    before={"src/spread.ts": TS_SP, "src/__tests__/spread.test.ts": TS_SP_T_B},
    after={"src/spread.ts": TS_SP, "src/__tests__/spread.test.ts": TS_SP_T_A},
)

# L04 move a test between files (pytest)
PY_STATS = '''
import math


def zscore(x, mean, sd):
    return (x - mean) / sd


def skew(xs):
    n = len(xs)
    m = sum(xs) / n
    s = math.sqrt(sum((x - m) ** 2 for x in xs) / n)
    return sum(((x - m) / s) ** 3 for x in xs) / n
'''
PY_STATS_T_B = '''
import pytest

from stats.core import skew, zscore


def test_zscore_basic():
    assert zscore(12, 10, 2) == 1.0


def test_zscore_negative():
    assert zscore(7, 10, 2) == -1.5


def test_skew_symmetric_is_zero():
    assert skew([-2.0, -1.0, 0.0, 1.0, 2.0]) == pytest.approx(0.0, abs=1e-12)


def test_skew_right_tail_positive():
    assert skew([1.0, 1.0, 1.0, 1.0, 10.0]) > 1.0
'''
PY_STATS_T_A = '''
from stats.core import zscore


def test_zscore_basic():
    assert zscore(12, 10, 2) == 1.0


def test_zscore_negative():
    assert zscore(7, 10, 2) == -1.5
'''
PY_SKEW_T = '''
import pytest

from stats.core import skew


def test_skew_symmetric_is_zero():
    assert skew([-2.0, -1.0, 0.0, 1.0, 2.0]) == pytest.approx(0.0, abs=1e-12)


def test_skew_right_tail_positive():
    assert skew([1.0, 1.0, 1.0, 1.0, 10.0]) > 1.0
'''
l04 = dict(
    slug="04-tests-moved-to-new-file", rules=[], framework="pytest",
    note="Skew tests moved verbatim from test_core.py to a new test_skew.py; same asserts, same count.",
    before={"stats/core.py": PY_STATS, "tests/test_core.py": PY_STATS_T_B},
    after={"stats/core.py": PY_STATS, "tests/test_core.py": PY_STATS_T_A, "tests/test_skew.py": PY_SKEW_T},
)

# L05 skipif with issue link (pytest)
PY_IO = '''
import csv


def load_prices(path):
    with open(path, newline="") as fh:
        return [(row["date"], float(row["close"])) for row in csv.DictReader(fh)]
'''
PY_IO_T_B = '''
from marketdata.io import load_prices


def test_load_prices(tmp_path):
    p = tmp_path / "px.csv"
    p.write_text("date,close\\n2024-01-02,10.5\\n2024-01-03,10.75\\n")
    assert load_prices(p) == [("2024-01-02", 10.5), ("2024-01-03", 10.75)]


def test_load_prices_locked_file_is_readable(tmp_path):
    p = tmp_path / "px.csv"
    p.write_text("date,close\\n2024-01-02,1.0\\n")
    p.chmod(0o444)
    assert load_prices(p)[0][1] == 1.0
'''
PY_IO_T_A = '''
import sys

import pytest

from marketdata.io import load_prices


def test_load_prices(tmp_path):
    p = tmp_path / "px.csv"
    p.write_text("date,close\\n2024-01-02,10.5\\n2024-01-03,10.75\\n")
    assert load_prices(p) == [("2024-01-02", 10.5), ("2024-01-03", 10.75)]


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="flaky on Windows, chmod semantics differ, see #412",
)
def test_load_prices_locked_file_is_readable(tmp_path):
    p = tmp_path / "px.csv"
    p.write_text("date,close\\n2024-01-02,1.0\\n")
    p.chmod(0o444)
    assert load_prices(p)[0][1] == 1.0
'''
l05 = dict(
    slug="05-skipif-with-issue-link", rules=[], framework="pytest",
    note="Platform-conditioned skipif whose reason cites issue #412 for a Windows-only chmod difference.",
    before={"marketdata/io.py": PY_IO, "tests/test_io.py": PY_IO_T_B},
    after={"marketdata/io.py": PY_IO, "tests/test_io.py": PY_IO_T_A},
)

# L06 delete feature + its tests (jest)
TS_LEG = '''
export function legacyVol(prices: number[]): number {
  const m = prices.reduce((a, b) => a + b, 0) / prices.length;
  return Math.sqrt(prices.reduce((a, p) => a + (p - m) ** 2, 0) / prices.length);
}
'''
TS_LEG_T = '''
import { legacyVol } from '../legacyVol';

describe('legacyVol', () => {
  it('is zero for a flat series', () => {
    expect(legacyVol([5, 5, 5])).toBe(0);
  });

  it('matches population stdev', () => {
    expect(legacyVol([2, 4, 4, 4, 5, 5, 7, 9])).toBeCloseTo(2, 10);
  });
});
'''
TS_INDEX_B = '''
export { legacyVol } from './legacyVol';
export { sma } from './indicators';
'''
TS_INDEX_A = '''
export { sma } from './indicators';
'''
l06 = dict(
    slug="06-feature-removed-with-its-tests", rules=[], framework="jest",
    note="Deprecated legacyVol module, its re-export and its test file all deleted in one commit.",
    before={"src/legacyVol.ts": TS_LEG, "src/__tests__/legacyVol.test.ts": TS_LEG_T, "src/index.ts": TS_INDEX_B,
            "src/indicators.ts": "export function sma(v: number[], w: number): number[] {\n  return v.slice(w - 1).map((_, i) => v.slice(i, i + w).reduce((a, b) => a + b, 0) / w);\n}\n"},
    after={"src/index.ts": TS_INDEX_A,
           "src/indicators.ts": "export function sma(v: number[], w: number): number[] {\n  return v.slice(w - 1).map((_, i) => v.slice(i, i + w).reduce((a, b) => a + b, 0) / w);\n}\n"},
)

# L07 refactor helper to fixture (pytest)
PY_LEDGER = '''
class Ledger:
    def __init__(self):
        self.entries = []

    def post(self, account, amount):
        self.entries.append((account, amount))

    def balance(self, account):
        return sum(a for acc, a in self.entries if acc == account)

    def total(self):
        return sum(a for _, a in self.entries)
'''
PY_LEDGER_T_B = '''
import pytest

from accounting.ledger import Ledger


def test_balance_by_account():
    lg = Ledger()
    lg.post("cash", 100)
    lg.post("cash", -30)
    lg.post("fees", 5)
    assert lg.balance("cash") == 70
    assert lg.balance("fees") == 5


def test_total_is_net():
    lg = Ledger()
    lg.post("cash", 100)
    lg.post("cash", -30)
    lg.post("fees", 5)
    assert lg.total() == 75


def test_unknown_account_is_zero():
    lg = Ledger()
    lg.post("cash", 100)
    lg.post("cash", -30)
    lg.post("fees", 5)
    assert lg.balance("nope") == 0
'''
PY_LEDGER_T_A = '''
import pytest

from accounting.ledger import Ledger


@pytest.fixture
def ledger():
    lg = Ledger()
    lg.post("cash", 100)
    lg.post("cash", -30)
    lg.post("fees", 5)
    return lg


def test_balance_by_account(ledger):
    assert ledger.balance("cash") == 70
    assert ledger.balance("fees") == 5


def test_total_is_net(ledger):
    assert ledger.total() == 75


def test_unknown_account_is_zero(ledger):
    assert ledger.balance("nope") == 0
'''
l07 = dict(
    slug="07-setup-extracted-to-fixture", rules=[], framework="pytest",
    note="Repeated setup moved into a fixture; all four original asserts are still present.",
    before={"accounting/ledger.py": PY_LEDGER, "tests/test_ledger.py": PY_LEDGER_T_B},
    after={"accounting/ledger.py": PY_LEDGER, "tests/test_ledger.py": PY_LEDGER_T_A},
)

# L08 behaviour change: source + expected together (pytest)
PY_COMM_B = '''
def commission(shares, price):
    gross = shares * price
    return max(1.0, gross * 0.0005)
'''
PY_COMM_A = '''
def commission(shares, price):
    gross = shares * price
    return max(0.35, gross * 0.0003)
'''
PY_COMM_T_B = '''
import pytest

from trading.commission import commission


def test_minimum_commission():
    assert commission(10, 5.0) == 1.0


def test_proportional_commission():
    assert commission(1000, 50.0) == pytest.approx(25.0)
'''
PY_COMM_T_A = '''
import pytest

from trading.commission import commission


def test_minimum_commission():
    assert commission(10, 5.0) == 0.35


def test_proportional_commission():
    assert commission(1000, 50.0) == pytest.approx(15.0)
'''
l08 = dict(
    slug="08-fee-schedule-change-source-and-tests", rules=[], framework="pytest",
    note="Fee schedule changed (min 1.0 -> 0.35, rate 5bp -> 3bp) and expected values updated in the same diff.",
    before={"trading/commission.py": PY_COMM_B, "tests/test_commission.py": PY_COMM_T_B},
    after={"trading/commission.py": PY_COMM_A, "tests/test_commission.py": PY_COMM_T_A},
)

# L09 behaviour change jest
JS_ROUND_B = '''
function roundLot(qty) {
  return Math.floor(qty / 100) * 100;
}

module.exports = { roundLot };
'''
JS_ROUND_A = '''
function roundLot(qty) {
  return Math.round(qty / 100) * 100;
}

module.exports = { roundLot };
'''
JS_ROUND_T_B = '''
const { roundLot } = require('../roundLot');

describe('roundLot', () => {
  test('rounds down to board lot', () => {
    expect(roundLot(260)).toBe(200);
  });

  test('exact lot unchanged', () => {
    expect(roundLot(300)).toBe(300);
  });
});
'''
JS_ROUND_T_A = JS_ROUND_T_B.replace("rounds down to board lot", "rounds to nearest board lot").replace("toBe(200)", "toBe(300)")
l09 = dict(
    slug="09-rounding-rule-change-with-expected", rules=[], framework="jest",
    note="roundLot switched from floor to round; the 260 case expectation 200 -> 300 changes with it.",
    before={"src/roundLot.js": JS_ROUND_B, "test/roundLot.test.js": JS_ROUND_T_B},
    after={"src/roundLot.js": JS_ROUND_A, "test/roundLot.test.js": JS_ROUND_T_A},
)

# L10 pure formatting (pytest) - black-style reflow
PY_VAR_T_B = '''
import pytest

from risk.var import historical_var


def test_var_95():
    r = [-0.05, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
    assert historical_var(r, 0.95) == pytest.approx(0.05, rel=1e-6, abs=1e-9)


def test_var_99():
    r = [-0.05, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
    assert historical_var(r, 0.99) == pytest.approx(0.05, rel=1e-6, abs=1e-9)
'''
PY_VAR_T_A = '''
import pytest

from risk.var import historical_var

RETURNS = [-0.05, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06]


def test_var_95():
    assert historical_var(RETURNS, 0.95) == pytest.approx(
        0.05,
        rel=1e-6,
        abs=1e-9,
    )


def test_var_99():
    assert historical_var(RETURNS, 0.99) == pytest.approx(
        0.05,
        rel=1e-6,
        abs=1e-9,
    )
'''
PY_VAR = '''
def historical_var(returns, conf):
    s = sorted(returns)
    idx = int((1 - conf) * len(s))
    return -s[idx]
'''
l10 = dict(
    slug="10-reflow-and-hoist-constant", rules=[], framework="pytest",
    note="Formatter-style reflow of approx() calls and a literal list hoisted to a constant; values and tolerances identical.",
    before={"risk/var.py": PY_VAR, "tests/test_var.py": PY_VAR_T_B},
    after={"risk/var.py": PY_VAR, "tests/test_var.py": PY_VAR_T_A},
)

# L11 non-test python file with skip/assert words
PY_LOADER_B = '''
def read_rows(lines):
    return [l.strip().split(",") for l in lines]
'''
PY_LOADER_A = '''
def assert_header(row, expected):
    if row != expected:
        raise ValueError(f"bad header: {row!r}")


def read_rows(lines, skip_rows=0, skip_blank=True):
    """Parse CSV-ish lines. skip_rows drops leading lines; xfail-style
    placeholders like '--' are kept as-is."""
    out = []
    for i, line in enumerate(lines):
        if i < skip_rows:
            continue
        if skip_blank and not line.strip():
            continue
        out.append(line.strip().split(","))
    return out
'''
l11 = dict(
    slug="11-source-file-with-skip-and-assert-words", rules=[], framework="pytest",
    note="Non-test module gains skip_rows, assert_header and a docstring mentioning xfail; no test files touched.",
    before={"etl/loader.py": PY_LOADER_B},
    after={"etl/loader.py": PY_LOADER_A},
)

# L12 jest: tighten digits + new test
TS_VAR = '''
export function parametricVar(sigma: number, z: number, notional: number): number {
  return sigma * z * notional;
}
'''
TS_VAR_T_B = '''
import { parametricVar } from '../parametricVar';

describe('parametricVar', () => {
  it('scales with notional', () => {
    expect(parametricVar(0.02, 1.645, 1_000_000)).toBeCloseTo(32900, 0);
  });
});
'''
TS_VAR_T_A = '''
import { parametricVar } from '../parametricVar';

describe('parametricVar', () => {
  it('scales with notional', () => {
    expect(parametricVar(0.02, 1.645, 1_000_000)).toBeCloseTo(32900, 6);
  });

  it('is zero with zero vol', () => {
    expect(parametricVar(0, 2.33, 5_000_000)).toBe(0);
  });
});
'''
l12 = dict(
    slug="12-digits-raised-plus-new-test", rules=[], framework="jest",
    note="toBeCloseTo digits 0 -> 6 (stricter) and a zero-vol test added.",
    before={"src/parametricVar.ts": TS_VAR, "src/__tests__/parametricVar.test.ts": TS_VAR_T_B},
    after={"src/parametricVar.ts": TS_VAR, "src/__tests__/parametricVar.test.ts": TS_VAR_T_A},
)

# L13 jest skip with issue link
JS_WS = '''
function backoffMs(attempt) {
  return Math.min(30000, 250 * 2 ** attempt);
}

module.exports = { backoffMs };
'''
JS_WS_T_B = '''
const { backoffMs } = require('../backoff');

test('first retry waits 250ms', () => {
  expect(backoffMs(0)).toBe(250);
});

test('backoff is capped at 30s', () => {
  expect(backoffMs(20)).toBe(30000);
});

test('reconnects after socket drop within timeout', async () => {
  const { connectWithRetry } = require('../ws');
  await expect(connectWithRetry('ws://localhost:9999', 3)).resolves.toBeDefined();
});
'''
JS_WS_T_A = JS_WS_T_B.replace(
    "test('reconnects after socket drop within timeout'",
    "// Flaky on shared CI runners: port 9999 sometimes still bound. Tracked in https://github.com/acme/mdfeed/issues/318\ntest.skip('reconnects after socket drop within timeout'")
l13 = dict(
    slug="13-skip-with-linked-issue", rules=[], framework="jest",
    note="One network-dependent test.skip with an explanatory comment and a GitHub issue URL.",
    before={"src/backoff.js": JS_WS, "test/backoff.test.js": JS_WS_T_B},
    after={"src/backoff.js": JS_WS, "test/backoff.test.js": JS_WS_T_A},
)

# L14 jest refactor to it.each preserving every case
TS_FEE = '''
export function makerFee(notional: number, tier: number): number {
  const bps = [10, 8, 6, 4][tier] ?? 10;
  return (notional * bps) / 1e4;
}
'''
TS_FEE_T_B = '''
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
'''
TS_FEE_T_A = '''
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
'''
l14 = dict(
    slug="14-collapsed-to-it-each", rules=[], framework="jest",
    note="Five near-identical tests folded into one it.each table with all five cases retained.",
    before={"src/fees.ts": TS_FEE, "src/__tests__/fees.test.ts": TS_FEE_T_B},
    after={"src/fees.ts": TS_FEE, "src/__tests__/fees.test.ts": TS_FEE_T_A},
)

# L15 pure rename of a test file (pytest)
PY_ANN = '''
def annualize(daily_return, days=252):
    return (1 + daily_return) ** days - 1
'''
PY_ANN_T = '''
import pytest

from analytics.annualize import annualize


def test_annualize_zero():
    assert annualize(0.0) == 0.0


def test_annualize_known():
    assert annualize(0.001) == pytest.approx(0.28643, rel=1e-4)
'''
l15 = dict(
    slug="15-test-file-renamed", rules=[], framework="pytest",
    note="tests/test_ann.py git-mv'd to tests/test_annualize.py with identical content.",
    before={"analytics/annualize.py": PY_ANN, "tests/test_ann.py": PY_ANN_T},
    after={"analytics/annualize.py": PY_ANN, "tests/test_annualize.py": PY_ANN_T},
)

# L16 non-test js with skip/only/assert words
JS_PAGER_B = '''
function page(items, n, size) {
  return items.slice(n * size, (n + 1) * size);
}

module.exports = { page };
'''
JS_PAGER_A = '''
function assertPositive(n, name) {
  if (!(n > 0)) throw new RangeError(`${name} must be positive`);
}

function page(items, n, size, { skip = 0, only = null } = {}) {
  assertPositive(size, 'size');
  const rows = only ? items.filter(only) : items;
  return rows.slice(skip + n * size, skip + (n + 1) * size);
}

module.exports = { page };
'''
l16 = dict(
    slug="16-js-source-uses-skip-only-assert", rules=[], framework="jest",
    note="Plain source module adds skip/only options and an assertPositive helper; no test file in the diff.",
    before={"src/pager.js": JS_PAGER_B},
    after={"src/pager.js": JS_PAGER_A},
)

LEGIT = [l01, l02, l03, l04, l05, l06, l07, l08, l09, l10, l11, l12, l13, l14, l15, l16]
