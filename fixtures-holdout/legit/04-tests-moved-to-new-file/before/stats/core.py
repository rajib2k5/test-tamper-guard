import math


def zscore(x, mean, sd):
    return (x - mean) / sd


def skew(xs):
    n = len(xs)
    m = sum(xs) / n
    s = math.sqrt(sum((x - m) ** 2 for x in xs) / n)
    return sum(((x - m) / s) ** 3 for x in xs) / n
