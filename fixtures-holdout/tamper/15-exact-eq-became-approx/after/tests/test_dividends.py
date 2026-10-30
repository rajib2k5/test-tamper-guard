import pytest

from fundamentals.dividends import dividend_yield, payout_ratio


def test_yield():
    assert dividend_yield(2.4, 80.0) == pytest.approx(0.03, abs=1e-2)


def test_payout_ratio():
    assert payout_ratio(1.5, 6.0) == 0.25


def test_payout_zero_earnings():
    assert payout_ratio(1.0, 0) == float("inf")
