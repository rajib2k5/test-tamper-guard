def historical_var(returns, conf):
    s = sorted(returns)
    idx = int((1 - conf) * len(s))
    return -s[idx]
