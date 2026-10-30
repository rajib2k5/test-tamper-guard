import pytest

from accounting.ledger import Ledger


@pytest.fixture
def ledger():
    lg = Ledger()
    lg.post("cash", 100)
    lg.post("cash", -30)
    lg.post("fees", 5)
    return lg


def test_balance_by_account(ledger):
    assert ledger.balance("cash") == 70
    assert ledger.balance("fees") == 5


def test_total_is_net(ledger):
    assert ledger.total() == 75


def test_unknown_account_is_zero(ledger):
    assert ledger.balance("nope") == 0
