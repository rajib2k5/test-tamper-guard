import pytest

from fx.convert import convert


def test_identity():
    assert convert(10, "USD", "USD") == 10


def test_usd_eur():
    assert convert(100, "USD", "EUR") == pytest.approx(92.0)


# def test_roundtrip_is_identity():
#     there = convert(100, "USD", "EUR")
#     back = convert(there, "EUR", "USD")
#     assert back == pytest.approx(100.0)


def test_missing_pair_raises():
    with pytest.raises(KeyError):
        convert(1, "EUR", "JPY")
