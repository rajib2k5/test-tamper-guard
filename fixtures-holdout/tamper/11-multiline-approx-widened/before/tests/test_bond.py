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
