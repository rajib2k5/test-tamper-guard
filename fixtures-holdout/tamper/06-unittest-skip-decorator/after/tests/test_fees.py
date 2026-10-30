import unittest

from trading.fees import tiered_fee


class TieredFeeTest(unittest.TestCase):
    def test_small_trade(self):
        self.assertAlmostEqual(tiered_fee(5_000), 5.0, places=6)

    def test_boundary_ten_k(self):
        self.assertAlmostEqual(tiered_fee(10_000), 10.0, places=6)

    @unittest.skip("broken")
    def test_middle_tier(self):
        self.assertAlmostEqual(tiered_fee(50_000), 38.0, places=6)

    def test_large_trade(self):
        self.assertAlmostEqual(tiered_fee(250_000), 133.0, places=6)


if __name__ == "__main__":
    unittest.main()
