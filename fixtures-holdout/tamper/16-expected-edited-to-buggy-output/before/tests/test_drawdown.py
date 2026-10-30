import pytest

from analytics.drawdown import max_drawdown


def test_monotonic_has_no_drawdown():
    assert max_drawdown([1, 2, 3, 4]) == 0.0


def test_single_dip():
    assert max_drawdown([100, 120, 90, 110]) == pytest.approx(-0.25)


def test_two_dips_takes_worst():
    equity = [100, 110, 99, 120, 84, 130]
    assert max_drawdown(equity) == pytest.approx(-0.30)
