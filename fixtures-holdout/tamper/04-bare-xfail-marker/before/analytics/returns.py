import math


def simple_returns(prices):
    return [b / a - 1.0 for a, b in zip(prices, prices[1:])]


def log_returns(prices):
    return [math.log(b / a) for a, b in zip(prices, prices[1:])]


def cumulative(returns):
    total = 1.0
    for r in returns:
        total *= 1.0 + r
    return total - 1.0
