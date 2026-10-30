import pytest

from accounting.ledger import Ledger


def test_balance_by_account():
    lg = Ledger()
    lg.post("cash", 100)
    lg.post("cash", -30)
    lg.post("fees", 5)
    assert lg.balance("cash") == 70
    assert lg.balance("fees") == 5


def test_total_is_net():
    lg = Ledger()
    lg.post("cash", 100)
    lg.post("cash", -30)
    lg.post("fees", 5)
    assert lg.total() == 75


def test_unknown_account_is_zero():
    lg = Ledger()
    lg.post("cash", 100)
    lg.post("cash", -30)
    lg.post("fees", 5)
    assert lg.balance("nope") == 0
