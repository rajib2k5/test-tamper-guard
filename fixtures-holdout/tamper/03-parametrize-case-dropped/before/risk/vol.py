import numpy as np


def realized_vol(returns, periods=252, ddof=1):
    r = np.asarray(returns, dtype=float)
    if r.size < 2:
        return float("nan")
    return float(np.std(r, ddof=ddof) * np.sqrt(periods))
