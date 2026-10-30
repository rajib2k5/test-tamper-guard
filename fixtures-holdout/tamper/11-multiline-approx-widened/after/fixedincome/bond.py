def bond_price(face, coupon_rate, ytm, years, freq=2):
    n = int(years * freq)
    c = face * coupon_rate / freq
    y = ytm / freq
    pv = sum(c / (1 + y) ** k for k in range(1, n + 1))
    return pv + face / (1 + y) ** n


def macaulay_duration(face, coupon_rate, ytm, years, freq=2):
    n = int(years * freq)
    c = face * coupon_rate / freq
    y = ytm / freq
    price = bond_price(face, coupon_rate, ytm, years, freq)
    w = sum(k * c / (1 + y) ** k for k in range(1, n + 1)) + n * face / (1 + y) ** n
    return w / price / freq
