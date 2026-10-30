import pytest

from sizing.kelly import half_kelly, kelly_fraction


def test_even_money_edge():
    assert kelly_fraction(0.6, 1.0) == pytest.approx(0.2, rel=1e-9)


def test_negative_edge_is_zero():
    assert kelly_fraction(0.4, 1.0) == 0.0


def test_half_kelly():
    assert half_kelly(0.55, 2.0) == pytest.approx(0.1625, rel=1e-9)
