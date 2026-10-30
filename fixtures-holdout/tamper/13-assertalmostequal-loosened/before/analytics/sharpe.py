import statistics


def sharpe(returns, rf=0.0, periods=252):
    ex = [r - rf / periods for r in returns]
    sd = statistics.stdev(ex)
    if sd == 0:
        return 0.0
    return statistics.mean(ex) / sd * periods ** 0.5
