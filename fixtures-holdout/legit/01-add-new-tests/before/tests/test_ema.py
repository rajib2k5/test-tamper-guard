import pytest

from indicators.ema import ema


def test_ema_first_value_is_seed():
    assert ema([5.0, 6.0], 3)[0] == 5.0


def test_ema_known_value():
    assert ema([10.0, 20.0, 30.0], 3)[-1] == pytest.approx(22.5)
