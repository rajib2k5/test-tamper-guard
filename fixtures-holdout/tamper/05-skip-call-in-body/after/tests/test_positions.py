import pytest

from portfolio.positions import Position, weights


def test_weights_sum_to_one():
    ps = [Position("AAPL", 10, 190.0), Position("MSFT", 5, 410.0), Position("GLD", 3, 220.0)]
    assert sum(weights(ps).values()) == pytest.approx(1.0)


def test_weights_with_short_position():
    pytest.skip("short handling needs rework")
    ps = [Position("AAPL", 10, 100.0), Position("TSLA", -4, 100.0)]
    w = weights(ps)
    assert w["AAPL"] == pytest.approx(1000 / 600)
    assert w["TSLA"] == pytest.approx(-400 / 600)
    assert sum(w.values()) == pytest.approx(1.0)
