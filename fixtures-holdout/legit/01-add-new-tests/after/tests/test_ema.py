import pytest

from indicators.ema import ema


def test_ema_first_value_is_seed():
    assert ema([5.0, 6.0], 3)[0] == 5.0


def test_ema_known_value():
    assert ema([10.0, 20.0, 30.0], 3)[-1] == pytest.approx(22.5)


def test_ema_constant_series_is_constant():
    assert ema([7.0] * 10, 5) == pytest.approx([7.0] * 10)


@pytest.mark.parametrize("span", [1, 2, 20])
def test_ema_preserves_length(span):
    assert len(ema([1.0, 2.0, 3.0, 4.0], span)) == 4
