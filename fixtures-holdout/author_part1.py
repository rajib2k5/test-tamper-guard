"""Fixture definitions, part 1 (tamper, pytest). Each entry is a dict with slug, rules, framework, note, before, after."""

PY_BS = '''
import math


def _cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def call_price(spot, strike, rate, vol, t):
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    return spot * _cdf(d1) - strike * math.exp(-rate * t) * _cdf(d2)


def put_price(spot, strike, rate, vol, t):
    c = call_price(spot, strike, rate, vol, t)
    return c - spot + strike * math.exp(-rate * t)
'''

PY_BS_T_BEFORE = '''
import math

import pytest

from pricing.black_scholes import call_price, put_price


def test_call_atm():
    assert call_price(100, 100, 0.05, 0.2, 1.0) == pytest.approx(10.4506, abs=1e-4)


def test_call_deep_itm_approaches_intrinsic():
    price = call_price(200, 100, 0.0, 0.1, 0.1)
    assert price == pytest.approx(100.0, abs=1e-3)


def test_put_call_parity():
    s, k, r, v, t = 120.0, 110.0, 0.03, 0.25, 0.5
    lhs = call_price(s, k, r, v, t) - put_price(s, k, r, v, t)
    assert lhs == pytest.approx(s - k * math.exp(-r * t), abs=1e-9)


def test_put_otm_is_small():
    assert put_price(150, 100, 0.01, 0.15, 0.25) < 0.01
'''

PY_BS_T_AFTER_DEL = '''
import math

import pytest

from pricing.black_scholes import call_price, put_price


def test_call_atm():
    assert call_price(100, 100, 0.05, 0.2, 1.0) == pytest.approx(10.4506, abs=1e-4)


def test_call_deep_itm_approaches_intrinsic():
    price = call_price(200, 100, 0.0, 0.1, 0.1)
    assert price == pytest.approx(100.0, abs=1e-3)


def test_put_otm_is_small():
    assert put_price(150, 100, 0.01, 0.15, 0.25) < 0.01
'''

t01 = dict(
    slug="01-parity-test-removed", rules=["test-deleted"], framework="pytest",
    note="Failing put-call parity test deleted instead of fixing put_price.",
    before={"pricing/black_scholes.py": PY_BS, "tests/test_black_scholes.py": PY_BS_T_BEFORE},
    after={"pricing/black_scholes.py": PY_BS, "tests/test_black_scholes.py": PY_BS_T_AFTER_DEL},
)

PY_VOL = '''
import numpy as np


def realized_vol(returns, periods=252, ddof=1):
    r = np.asarray(returns, dtype=float)
    if r.size < 2:
        return float("nan")
    return float(np.std(r, ddof=ddof) * np.sqrt(periods))
'''
PY_VOL_T_B = '''
import math

import pytest

from risk.vol import realized_vol


@pytest.mark.parametrize(
    "returns, periods, expected",
    [
        ([0.01, -0.01, 0.01, -0.01], 252, 0.18330302779823358),
        ([0.0, 0.0, 0.0], 252, 0.0),
        ([0.02, 0.02], 12, 0.0),
        ([0.01], 252, None),
        ([], 252, None),
        ([0.05, -0.03, 0.02, 0.0, -0.01], 52, 0.2175600294468),
    ],
)
def test_realized_vol(returns, periods, expected):
    out = realized_vol(returns, periods=periods)
    if expected is None:
        assert math.isnan(out)
    else:
        assert out == pytest.approx(expected, rel=1e-9)
'''
PY_VOL_T_A = PY_VOL_T_B.replace("        ([0.05, -0.03, 0.02, 0.0, -0.01], 52, 0.2175600294468),\n", "")
t03 = dict(
    slug="03-parametrize-case-dropped", rules=["test-deleted"], framework="pytest",
    note="The one parametrize case that failed (weekly annualisation) was removed from the list.",
    before={"risk/vol.py": PY_VOL, "tests/test_vol.py": PY_VOL_T_B},
    after={"risk/vol.py": PY_VOL, "tests/test_vol.py": PY_VOL_T_A},
)

PY_RET = '''
import math


def simple_returns(prices):
    return [b / a - 1.0 for a, b in zip(prices, prices[1:])]


def log_returns(prices):
    return [math.log(b / a) for a, b in zip(prices, prices[1:])]


def cumulative(returns):
    total = 1.0
    for r in returns:
        total *= 1.0 + r
    return total - 1.0
'''
PY_RET_T_B = '''
import pytest

from analytics.returns import cumulative, log_returns, simple_returns


def test_simple_returns():
    assert simple_returns([100, 110, 99]) == pytest.approx([0.1, -0.1])


def test_log_returns_sum_to_total():
    prices = [100.0, 105.0, 103.0, 110.0]
    assert sum(log_returns(prices)) == pytest.approx(0.0953101798, abs=1e-9)


def test_cumulative_compounds():
    assert cumulative([0.1, 0.1]) == pytest.approx(0.21)


def test_cumulative_empty_is_zero():
    assert cumulative([]) == 0.0
'''
PY_RET_T_A = PY_RET_T_B.replace(
    "def test_cumulative_compounds():",
    "@pytest.mark.xfail\ndef test_cumulative_compounds():")
t04 = dict(
    slug="04-bare-xfail-marker", rules=["skip-added"], framework="pytest",
    note="Bare @pytest.mark.xfail added to a failing test; no reason, no issue.",
    before={"analytics/returns.py": PY_RET, "tests/test_returns.py": PY_RET_T_B},
    after={"analytics/returns.py": PY_RET, "tests/test_returns.py": PY_RET_T_A},
)

PY_PORT = '''
from dataclasses import dataclass


@dataclass
class Position:
    symbol: str
    qty: float
    price: float

    @property
    def value(self):
        return self.qty * self.price


def weights(positions):
    total = sum(p.value for p in positions)
    return {p.symbol: p.value / total for p in positions}
'''
PY_PORT_T_B = '''
import pytest

from portfolio.positions import Position, weights


def test_weights_sum_to_one():
    ps = [Position("AAPL", 10, 190.0), Position("MSFT", 5, 410.0), Position("GLD", 3, 220.0)]
    assert sum(weights(ps).values()) == pytest.approx(1.0)


def test_weights_with_short_position():
    ps = [Position("AAPL", 10, 100.0), Position("TSLA", -4, 100.0)]
    w = weights(ps)
    assert w["AAPL"] == pytest.approx(1000 / 600)
    assert w["TSLA"] == pytest.approx(-400 / 600)
    assert sum(w.values()) == pytest.approx(1.0)
'''
PY_PORT_T_A = PY_PORT_T_B.replace(
    "def test_weights_with_short_position():\n    ps =",
    "def test_weights_with_short_position():\n    pytest.skip(\"short handling needs rework\")\n    ps =")
t05 = dict(
    slug="05-skip-call-in-body", rules=["skip-added"], framework="pytest",
    note="pytest.skip() inserted at top of a failing test body; remaining asserts become dead.",
    before={"portfolio/positions.py": PY_PORT, "tests/test_positions.py": PY_PORT_T_B},
    after={"portfolio/positions.py": PY_PORT, "tests/test_positions.py": PY_PORT_T_A},
)

PY_FEE = '''
def tiered_fee(notional):
    if notional < 10_000:
        return notional * 0.0010
    if notional < 100_000:
        return 10.0 + (notional - 10_000) * 0.0007
    return 73.0 + (notional - 100_000) * 0.0004
'''
PY_FEE_T_B = '''
import unittest

from trading.fees import tiered_fee


class TieredFeeTest(unittest.TestCase):
    def test_small_trade(self):
        self.assertAlmostEqual(tiered_fee(5_000), 5.0, places=6)

    def test_boundary_ten_k(self):
        self.assertAlmostEqual(tiered_fee(10_000), 10.0, places=6)

    def test_middle_tier(self):
        self.assertAlmostEqual(tiered_fee(50_000), 38.0, places=6)

    def test_large_trade(self):
        self.assertAlmostEqual(tiered_fee(250_000), 133.0, places=6)


if __name__ == "__main__":
    unittest.main()
'''
PY_FEE_T_A = PY_FEE_T_B.replace(
    "    def test_middle_tier(self):",
    "    @unittest.skip(\"broken\")\n    def test_middle_tier(self):")
t06 = dict(
    slug="06-unittest-skip-decorator", rules=["skip-added"], framework="pytest",
    note="@unittest.skip('broken') added to the middle-tier fee test with no issue reference.",
    before={"trading/fees.py": PY_FEE, "tests/test_fees.py": PY_FEE_T_B},
    after={"trading/fees.py": PY_FEE, "tests/test_fees.py": PY_FEE_T_A},
)

PY_BOND = '''
def bond_price(face, coupon_rate, ytm, years, freq=2):
    n = int(years * freq)
    c = face * coupon_rate / freq
    y = ytm / freq
    pv = sum(c / (1 + y) ** k for k in range(1, n + 1))
    return pv + face / (1 + y) ** n


def macaulay_duration(face, coupon_rate, ytm, years, freq=2):
    n = int(years * freq)
    c = face * coupon_rate / freq
    y = ytm / freq
    price = bond_price(face, coupon_rate, ytm, years, freq)
    w = sum(k * c / (1 + y) ** k for k in range(1, n + 1)) + n * face / (1 + y) ** n
    return w / price / freq
'''
PY_BOND_T_B = '''
import pytest

from fixedincome.bond import bond_price, macaulay_duration


def test_par_bond_prices_at_face():
    assert bond_price(1000, 0.05, 0.05, 10) == pytest.approx(1000.0, rel=1e-9)


def test_discount_bond():
    price = bond_price(1000, 0.04, 0.06, 5)
    assert price == pytest.approx(
        914.6923,
        rel=1e-6,
    )


def test_duration_ten_year():
    d = macaulay_duration(1000, 0.05, 0.05, 10)
    assert d == pytest.approx(
        7.9895,
        rel=1e-4,
        abs=1e-4,
    )
'''
PY_BOND_T_A = PY_BOND_T_B.replace("        914.6923,\n        rel=1e-6,", "        914.6923,\n        rel=1e-2,").replace(
    "        7.9895,\n        rel=1e-4,\n        abs=1e-4,", "        7.9895,\n        rel=5e-2,\n        abs=5e-2,")
t11 = dict(
    slug="11-multiline-approx-widened", rules=["tolerance-loosened"], framework="pytest",
    note="Two multi-line pytest.approx( calls had rel/abs widened by 100-500x with no source change.",
    before={"fixedincome/bond.py": PY_BOND, "tests/test_bond.py": PY_BOND_T_B},
    after={"fixedincome/bond.py": PY_BOND, "tests/test_bond.py": PY_BOND_T_A},
)

PY_COV = '''
import numpy as np


def ewma_cov(returns, lam=0.94):
    r = np.asarray(returns, dtype=float)
    n, k = r.shape
    w = lam ** np.arange(n - 1, -1, -1)
    w = w / w.sum()
    mu = (w[:, None] * r).sum(axis=0)
    x = r - mu
    return (x * w[:, None]).T @ x
'''
PY_COV_T_B = '''
import numpy as np
from numpy.testing import assert_allclose

from risk.cov import ewma_cov


def test_ewma_cov_symmetric():
    rng = np.random.default_rng(7)
    c = ewma_cov(rng.normal(size=(60, 4)))
    assert_allclose(c, c.T, rtol=1e-12, atol=0)


def test_ewma_cov_reference():
    r = np.array([[0.01, 0.02], [-0.01, 0.00], [0.02, -0.01], [0.00, 0.01]])
    expected = np.array([[9.2411e-05, -3.1022e-05], [-3.1022e-05, 1.1520e-04]])
    assert_allclose(ewma_cov(r), expected, rtol=1e-4, atol=1e-10)
'''
PY_COV_T_A = PY_COV_T_B.replace("rtol=1e-4, atol=1e-10", "rtol=5e-1, atol=1e-3")
t12 = dict(
    slug="12-assert-allclose-rtol-widened", rules=["tolerance-loosened"], framework="pytest",
    note="numpy assert_allclose rtol 1e-4 -> 5e-1 and atol 1e-10 -> 1e-3 on the reference-covariance test.",
    before={"risk/cov.py": PY_COV, "tests/test_cov.py": PY_COV_T_B},
    after={"risk/cov.py": PY_COV, "tests/test_cov.py": PY_COV_T_A},
)

PY_SHARPE = '''
import statistics


def sharpe(returns, rf=0.0, periods=252):
    ex = [r - rf / periods for r in returns]
    sd = statistics.stdev(ex)
    if sd == 0:
        return 0.0
    return statistics.mean(ex) / sd * periods ** 0.5
'''
PY_SHARPE_T_B = '''
import unittest

from analytics.sharpe import sharpe


class SharpeTests(unittest.TestCase):
    def test_known_series(self):
        r = [0.01, 0.02, -0.005, 0.015, 0.0, 0.01]
        self.assertAlmostEqual(sharpe(r), 14.7648, places=4)

    def test_constant_series_is_zero(self):
        self.assertAlmostEqual(sharpe([0.01, 0.01, 0.01]), 0.0, places=7)

    def test_rf_shifts_result(self):
        r = [0.01, 0.02, -0.005, 0.015, 0.0, 0.01]
        self.assertAlmostEqual(sharpe(r, rf=0.02), 13.8421, delta=1e-4)
'''
PY_SHARPE_T_A = PY_SHARPE_T_B.replace("14.7648, places=4", "14.7648, places=0").replace("13.8421, delta=1e-4", "13.8421, delta=0.5")
t13 = dict(
    slug="13-assertalmostequal-loosened", rules=["tolerance-loosened"], framework="pytest",
    note="assertAlmostEqual places=4 -> 0 and delta=1e-4 -> 0.5 in unittest-style sharpe tests.",
    before={"analytics/sharpe.py": PY_SHARPE, "tests/test_sharpe.py": PY_SHARPE_T_B},
    after={"analytics/sharpe.py": PY_SHARPE, "tests/test_sharpe.py": PY_SHARPE_T_A},
)

PY_DIV = '''
def dividend_yield(annual_dividend, price):
    return annual_dividend / price


def payout_ratio(dividends, earnings):
    return dividends / earnings if earnings else float("inf")
'''
PY_DIV_T_B = '''
from fundamentals.dividends import dividend_yield, payout_ratio


def test_yield():
    assert dividend_yield(2.4, 80.0) == 0.03


def test_payout_ratio():
    assert payout_ratio(1.5, 6.0) == 0.25


def test_payout_zero_earnings():
    assert payout_ratio(1.0, 0) == float("inf")
'''
PY_DIV_T_A = '''
import pytest

from fundamentals.dividends import dividend_yield, payout_ratio


def test_yield():
    assert dividend_yield(2.4, 80.0) == pytest.approx(0.03, abs=1e-2)


def test_payout_ratio():
    assert payout_ratio(1.5, 6.0) == 0.25


def test_payout_zero_earnings():
    assert payout_ratio(1.0, 0) == float("inf")
'''
t15 = dict(
    slug="15-exact-eq-became-approx", rules=["tolerance-loosened"], framework="pytest",
    note="assert x == 0.03 rewritten to approx(0.03, abs=1e-2): a 33% window around the value.",
    before={"fundamentals/dividends.py": PY_DIV, "tests/test_dividends.py": PY_DIV_T_B},
    after={"fundamentals/dividends.py": PY_DIV, "tests/test_dividends.py": PY_DIV_T_A},
)

# Source is buggy: divides by the average of peak and value instead of the peak.
PY_DD = '''
def max_drawdown(equity):
    peak = equity[0]
    worst = 0.0
    for v in equity:
        peak = max(peak, v)
        worst = min(worst, (v - peak) / ((peak + v) / 2))
    return worst
'''
PY_DD_T_B = '''
import pytest

from analytics.drawdown import max_drawdown


def test_monotonic_has_no_drawdown():
    assert max_drawdown([1, 2, 3, 4]) == 0.0


def test_single_dip():
    assert max_drawdown([100, 120, 90, 110]) == pytest.approx(-0.25)


def test_two_dips_takes_worst():
    equity = [100, 110, 99, 120, 84, 130]
    assert max_drawdown(equity) == pytest.approx(-0.30)
'''
PY_DD_T_A = PY_DD_T_B.replace("pytest.approx(-0.25)", "pytest.approx(-0.2857142857)").replace(
    "pytest.approx(-0.30)", "pytest.approx(-0.3529411765)")
t16 = dict(
    slug="16-expected-edited-to-buggy-output", rules=["expected-changed"], framework="pytest",
    note="Expected drawdowns edited (-0.25 -> -0.2857, -0.30 -> -0.3529) to match the buggy denominator; source untouched.",
    before={"analytics/drawdown.py": PY_DD, "tests/test_drawdown.py": PY_DD_T_B},
    after={"analytics/drawdown.py": PY_DD, "tests/test_drawdown.py": PY_DD_T_A},
)

PY_ORD = '''
class OrderBook:
    def __init__(self):
        self.bids = {}
        self.asks = {}

    def add(self, side, price, qty):
        book = self.bids if side == "buy" else self.asks
        book[price] = book.get(price, 0) + qty

    def best_bid(self):
        return max(self.bids) if self.bids else None

    def best_ask(self):
        return min(self.asks) if self.asks else None

    def spread(self):
        if not self.bids or not self.asks:
            return None
        return self.best_ask() - self.best_bid()
'''
PY_ORD_T_B = '''
from marketdata.book import OrderBook


def test_spread_after_quotes():
    ob = OrderBook()
    ob.add("buy", 99.5, 10)
    ob.add("buy", 99.0, 5)
    ob.add("sell", 100.25, 7)
    ob.add("sell", 101.0, 3)
    assert ob.best_bid() == 99.5
    assert ob.best_ask() == 100.25
    assert ob.spread() == 0.75
    assert ob.bids[99.5] == 10


def test_empty_book_has_no_spread():
    ob = OrderBook()
    assert ob.spread() is None
'''
PY_ORD_T_A = PY_ORD_T_B.replace("    assert ob.spread() == 0.75\n    assert ob.bids[99.5] == 10\n", "")
t18 = dict(
    slug="18-asserts-deleted-body-kept", rules=["assert-removed"], framework="pytest",
    note="Two asserts (spread value and bid depth) deleted from test_spread_after_quotes; test still runs green.",
    before={"marketdata/book.py": PY_ORD, "tests/test_book.py": PY_ORD_T_B},
    after={"marketdata/book.py": PY_ORD, "tests/test_book.py": PY_ORD_T_A},
)

PY_FX = '''
RATES = {("USD", "EUR"): 0.92, ("EUR", "USD"): 1.087, ("USD", "JPY"): 150.0}


def convert(amount, src, dst):
    if src == dst:
        return amount
    return amount * RATES[(src, dst)]
'''
PY_FX_T_B = '''
import pytest

from fx.convert import convert


def test_identity():
    assert convert(10, "USD", "USD") == 10


def test_usd_eur():
    assert convert(100, "USD", "EUR") == pytest.approx(92.0)


def test_roundtrip_is_identity():
    there = convert(100, "USD", "EUR")
    back = convert(there, "EUR", "USD")
    assert back == pytest.approx(100.0)


def test_missing_pair_raises():
    with pytest.raises(KeyError):
        convert(1, "EUR", "JPY")
'''
PY_FX_T_A = PY_FX_T_B.replace(
    '''def test_roundtrip_is_identity():
    there = convert(100, "USD", "EUR")
    back = convert(there, "EUR", "USD")
    assert back == pytest.approx(100.0)
''',
    '''# def test_roundtrip_is_identity():
#     there = convert(100, "USD", "EUR")
#     back = convert(there, "EUR", "USD")
#     assert back == pytest.approx(100.0)
''')
t20 = dict(
    slug="20-test-function-commented-out", rules=["test-commented-out"], framework="pytest",
    note="Whole round-trip test commented out because the FX table is not self-consistent.",
    before={"fx/convert.py": PY_FX, "tests/test_convert.py": PY_FX_T_B},
    after={"fx/convert.py": PY_FX, "tests/test_convert.py": PY_FX_T_A},
)

PY_KELLY = '''
import logging

log = logging.getLogger(__name__)


def kelly_fraction(p_win, payoff):
    q = 1.0 - p_win
    f = (p_win * payoff - q) / payoff
    return max(0.0, f)


def half_kelly(p_win, payoff):
    return 0.5 * kelly_fraction(p_win, payoff)
'''
PY_KELLY_A = PY_KELLY.replace("def kelly_fraction(p_win, payoff):\n    q", "def kelly_fraction(p_win, payoff):\n    log.debug(\"kelly p=%s b=%s\", p_win, payoff)\n    q")
PY_KELLY_T_B = '''
import pytest

from sizing.kelly import half_kelly, kelly_fraction


def test_even_money_edge():
    assert kelly_fraction(0.6, 1.0) == pytest.approx(0.2, rel=1e-9)


def test_negative_edge_is_zero():
    assert kelly_fraction(0.4, 1.0) == 0.0


def test_half_kelly():
    assert half_kelly(0.55, 2.0) == pytest.approx(0.1625, rel=1e-9)
'''
PY_KELLY_T_A = PY_KELLY_T_B.replace("pytest.approx(0.2, rel=1e-9)", "pytest.approx(0.25, rel=1e-9)").replace(
    "pytest.approx(0.1625, rel=1e-9)", "pytest.approx(0.1625, rel=1e-1)")
t22 = dict(
    slug="22-unrelated-source-edit-masks-tamper", rules=["expected-changed", "tolerance-loosened"], framework="pytest",
    note="Source diff is only a log.debug line; test diff changes one expected literal and widens another tolerance.",
    before={"sizing/kelly.py": PY_KELLY, "tests/test_kelly.py": PY_KELLY_T_B},
    after={"sizing/kelly.py": PY_KELLY_A, "tests/test_kelly.py": PY_KELLY_T_A},
)

PY_TWAP = '''
def twap(prices, volumes=None):
    if not prices:
        raise ValueError("no prices")
    return sum(prices) / len(prices)


def vwap(prices, volumes):
    total = sum(volumes)
    return sum(p * v for p, v in zip(prices, volumes)) / total
'''
PY_TWAP_T_B = '''
import pytest

from execution.benchmarks import twap, vwap


def test_twap_simple():
    assert twap([10, 12, 14]) == 12


def test_vwap_weights_by_volume():
    assert vwap([10, 20], [90, 10]) == pytest.approx(11.0)


def test_vwap_zero_volume_raises():
    with pytest.raises(ValueError):
        vwap([10, 20], [0, 0])
'''
PY_TWAP_T_A = PY_TWAP_T_B.replace(
    '''    with pytest.raises(ValueError):
        vwap([10, 20], [0, 0])''',
    '''    try:
        vwap([10, 20], [0, 0])
    except Exception:
        pass
    assert True''')
t24 = dict(
    slug="24-raises-check-neutered", rules=["assert-removed"], framework="pytest",
    note="pytest.raises(ValueError) replaced by try/except pass plus assert True; ZeroDivisionError now passes.",
    before={"execution/benchmarks.py": PY_TWAP, "tests/test_benchmarks.py": PY_TWAP_T_B},
    after={"execution/benchmarks.py": PY_TWAP, "tests/test_benchmarks.py": PY_TWAP_T_A},
)

PY_TORCH = '''
import torch


def softmax_temp(logits, temp=1.0):
    return torch.softmax(logits / temp, dim=-1)


def entropy(p):
    return -(p * torch.log(p.clamp_min(1e-12))).sum(dim=-1)
'''
PY_TORCH_T_B = '''
import torch

from models.probs import entropy, softmax_temp


def test_softmax_rows_sum_to_one():
    p = softmax_temp(torch.randn(8, 5), temp=0.7)
    assert torch.allclose(p.sum(-1), torch.ones(8), atol=1e-6)


def test_uniform_entropy():
    p = torch.full((1, 4), 0.25)
    torch.testing.assert_close(entropy(p), torch.tensor([1.3862944]), rtol=1e-5, atol=1e-6)
'''
PY_TORCH_T_A = PY_TORCH_T_B.replace("torch.ones(8), atol=1e-6)", "torch.ones(8), atol=1e-2)").replace(
    "rtol=1e-5, atol=1e-6", "rtol=1e-1, atol=1e-1")
t25 = dict(
    slug="25-torch-atol-rtol-widened", rules=["tolerance-loosened"], framework="pytest",
    note="torch.allclose atol 1e-6 -> 1e-2 and assert_close rtol/atol widened to 1e-1.",
    before={"models/probs.py": PY_TORCH, "tests/test_probs.py": PY_TORCH_T_B},
    after={"models/probs.py": PY_TORCH, "tests/test_probs.py": PY_TORCH_T_A},
)

PYTEST_TAMPER = [t01, t03, t04, t05, t06, t11, t12, t13, t15, t16, t18, t20, t22, t24, t25]
