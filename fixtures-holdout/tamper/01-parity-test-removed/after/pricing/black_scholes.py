import math


def _cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def call_price(spot, strike, rate, vol, t):
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    return spot * _cdf(d1) - strike * math.exp(-rate * t) * _cdf(d2)


def put_price(spot, strike, rate, vol, t):
    c = call_price(spot, strike, rate, vol, t)
    return c - spot + strike * math.exp(-rate * t)
