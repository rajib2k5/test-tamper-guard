import logging

log = logging.getLogger(__name__)


def kelly_fraction(p_win, payoff):
    log.debug("kelly p=%s b=%s", p_win, payoff)
    q = 1.0 - p_win
    f = (p_win * payoff - q) / payoff
    return max(0.0, f)


def half_kelly(p_win, payoff):
    return 0.5 * kelly_fraction(p_win, payoff)
