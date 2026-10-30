import numpy as np


def ewma_cov(returns, lam=0.94):
    r = np.asarray(returns, dtype=float)
    n, k = r.shape
    w = lam ** np.arange(n - 1, -1, -1)
    w = w / w.sum()
    mu = (w[:, None] * r).sum(axis=0)
    x = r - mu
    return (x * w[:, None]).T @ x
