class OrderBook:
    def __init__(self):
        self.bids = {}
        self.asks = {}

    def add(self, side, price, qty):
        book = self.bids if side == "buy" else self.asks
        book[price] = book.get(price, 0) + qty

    def best_bid(self):
        return max(self.bids) if self.bids else None

    def best_ask(self):
        return min(self.asks) if self.asks else None

    def spread(self):
        if not self.bids or not self.asks:
            return None
        return self.best_ask() - self.best_bid()
