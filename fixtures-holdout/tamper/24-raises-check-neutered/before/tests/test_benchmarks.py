import pytest

from execution.benchmarks import twap, vwap


def test_twap_simple():
    assert twap([10, 12, 14]) == 12


def test_vwap_weights_by_volume():
    assert vwap([10, 20], [90, 10]) == pytest.approx(11.0)


def test_vwap_zero_volume_raises():
    with pytest.raises(ValueError):
        vwap([10, 20], [0, 0])
