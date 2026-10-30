import pytest

from risk.var import historical_var


def test_var_95():
    r = [-0.05, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
    assert historical_var(r, 0.95) == pytest.approx(0.05, rel=1e-6, abs=1e-9)


def test_var_99():
    r = [-0.05, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
    assert historical_var(r, 0.99) == pytest.approx(0.05, rel=1e-6, abs=1e-9)
