def max_drawdown(equity):
    peak = equity[0]
    worst = 0.0
    for v in equity:
        peak = max(peak, v)
        worst = min(worst, (v - peak) / ((peak + v) / 2))
    return worst
