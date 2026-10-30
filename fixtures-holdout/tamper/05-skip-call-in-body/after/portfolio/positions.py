from dataclasses import dataclass


@dataclass
class Position:
    symbol: str
    qty: float
    price: float

    @property
    def value(self):
        return self.qty * self.price


def weights(positions):
    total = sum(p.value for p in positions)
    return {p.symbol: p.value / total for p in positions}
