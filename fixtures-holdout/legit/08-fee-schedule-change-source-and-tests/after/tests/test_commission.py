import pytest

from trading.commission import commission


def test_minimum_commission():
    assert commission(10, 5.0) == 0.35


def test_proportional_commission():
    assert commission(1000, 50.0) == pytest.approx(15.0)
