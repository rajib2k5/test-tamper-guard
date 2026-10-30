import numpy as np
from numpy.testing import assert_allclose

from risk.cov import ewma_cov


def test_ewma_cov_symmetric():
    rng = np.random.default_rng(7)
    c = ewma_cov(rng.normal(size=(60, 4)))
    assert_allclose(c, c.T, rtol=1e-12, atol=0)


def test_ewma_cov_reference():
    r = np.array([[0.01, 0.02], [-0.01, 0.00], [0.02, -0.01], [0.00, 0.01]])
    expected = np.array([[9.2411e-05, -3.1022e-05], [-3.1022e-05, 1.1520e-04]])
    assert_allclose(ewma_cov(r), expected, rtol=1e-4, atol=1e-10)
