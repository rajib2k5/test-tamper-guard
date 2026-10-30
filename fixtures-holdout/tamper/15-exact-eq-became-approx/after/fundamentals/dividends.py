def dividend_yield(annual_dividend, price):
    return annual_dividend / price


def payout_ratio(dividends, earnings):
    return dividends / earnings if earnings else float("inf")
