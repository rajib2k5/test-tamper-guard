def tiered_fee(notional):
    if notional < 10_000:
        return notional * 0.0010
    if notional < 100_000:
        return 10.0 + (notional - 10_000) * 0.0007
    return 73.0 + (notional - 100_000) * 0.0004
