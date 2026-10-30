import pytest

from valuation.npv import irr, npv


def test_npv_zero_rate_is_sum():
    assert npv(0.0, [-100, 60, 60]) == pytest.approx(20.0, abs=1e-9)


def test_irr_roundtrip():
    cfs = [-1000, 300, 400, 500]
    r = irr(cfs)
    assert npv(r, cfs) == pytest.approx(0.0, abs=1e-8)
