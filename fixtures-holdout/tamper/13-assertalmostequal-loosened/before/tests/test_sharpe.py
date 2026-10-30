import unittest

from analytics.sharpe import sharpe


class SharpeTests(unittest.TestCase):
    def test_known_series(self):
        r = [0.01, 0.02, -0.005, 0.015, 0.0, 0.01]
        self.assertAlmostEqual(sharpe(r), 14.7648, places=4)

    def test_constant_series_is_zero(self):
        self.assertAlmostEqual(sharpe([0.01, 0.01, 0.01]), 0.0, places=7)

    def test_rf_shifts_result(self):
        r = [0.01, 0.02, -0.005, 0.015, 0.0, 0.01]
        self.assertAlmostEqual(sharpe(r, rf=0.02), 13.8421, delta=1e-4)
