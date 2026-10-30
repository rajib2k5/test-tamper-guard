RATES = {("USD", "EUR"): 0.92, ("EUR", "USD"): 1.087, ("USD", "JPY"): 150.0}


def convert(amount, src, dst):
    if src == dst:
        return amount
    return amount * RATES[(src, dst)]
