import pytest

from trading.commission import commission


def test_minimum_commission():
    assert commission(10, 5.0) == 1.0


def test_proportional_commission():
    assert commission(1000, 50.0) == pytest.approx(25.0)
