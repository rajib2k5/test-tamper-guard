def commission(shares, price):
    gross = shares * price
    return max(1.0, gross * 0.0005)
