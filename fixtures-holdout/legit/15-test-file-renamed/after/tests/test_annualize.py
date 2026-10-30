import pytest

from analytics.annualize import annualize


def test_annualize_zero():
    assert annualize(0.0) == 0.0


def test_annualize_known():
    assert annualize(0.001) == pytest.approx(0.28643, rel=1e-4)
