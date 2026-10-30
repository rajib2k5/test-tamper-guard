from marketdata.book import OrderBook


def test_spread_after_quotes():
    ob = OrderBook()
    ob.add("buy", 99.5, 10)
    ob.add("buy", 99.0, 5)
    ob.add("sell", 100.25, 7)
    ob.add("sell", 101.0, 3)
    assert ob.best_bid() == 99.5
    assert ob.best_ask() == 100.25
    assert ob.spread() == 0.75
    assert ob.bids[99.5] == 10


def test_empty_book_has_no_spread():
    ob = OrderBook()
    assert ob.spread() is None
