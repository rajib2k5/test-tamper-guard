import pytest

from analytics.returns import cumulative, log_returns, simple_returns


def test_simple_returns():
    assert simple_returns([100, 110, 99]) == pytest.approx([0.1, -0.1])


def test_log_returns_sum_to_total():
    prices = [100.0, 105.0, 103.0, 110.0]
    assert sum(log_returns(prices)) == pytest.approx(0.0953101798, abs=1e-9)


@pytest.mark.xfail
def test_cumulative_compounds():
    assert cumulative([0.1, 0.1]) == pytest.approx(0.21)


def test_cumulative_empty_is_zero():
    assert cumulative([]) == 0.0
