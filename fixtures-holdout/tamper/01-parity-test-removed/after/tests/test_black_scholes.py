import math

import pytest

from pricing.black_scholes import call_price, put_price


def test_call_atm():
    assert call_price(100, 100, 0.05, 0.2, 1.0) == pytest.approx(10.4506, abs=1e-4)


def test_call_deep_itm_approaches_intrinsic():
    price = call_price(200, 100, 0.0, 0.1, 0.1)
    assert price == pytest.approx(100.0, abs=1e-3)


def test_put_otm_is_small():
    assert put_price(150, 100, 0.01, 0.15, 0.25) < 0.01
