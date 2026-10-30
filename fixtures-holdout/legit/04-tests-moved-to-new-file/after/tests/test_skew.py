import pytest

from stats.core import skew


def test_skew_symmetric_is_zero():
    assert skew([-2.0, -1.0, 0.0, 1.0, 2.0]) == pytest.approx(0.0, abs=1e-12)


def test_skew_right_tail_positive():
    assert skew([1.0, 1.0, 1.0, 1.0, 10.0]) > 1.0
