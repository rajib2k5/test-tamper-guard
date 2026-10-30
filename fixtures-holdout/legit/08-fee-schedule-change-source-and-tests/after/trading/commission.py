def commission(shares, price):
    gross = shares * price
    return max(0.35, gross * 0.0003)
