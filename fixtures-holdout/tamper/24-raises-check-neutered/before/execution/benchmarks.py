def twap(prices, volumes=None):
    if not prices:
        raise ValueError("no prices")
    return sum(prices) / len(prices)


def vwap(prices, volumes):
    total = sum(volumes)
    return sum(p * v for p, v in zip(prices, volumes)) / total
