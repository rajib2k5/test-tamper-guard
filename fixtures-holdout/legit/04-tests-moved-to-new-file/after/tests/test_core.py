from stats.core import zscore


def test_zscore_basic():
    assert zscore(12, 10, 2) == 1.0


def test_zscore_negative():
    assert zscore(7, 10, 2) == -1.5
