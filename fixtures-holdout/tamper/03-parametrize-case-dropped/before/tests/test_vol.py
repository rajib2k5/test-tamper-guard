import math

import pytest

from risk.vol import realized_vol


@pytest.mark.parametrize(
    "returns, periods, expected",
    [
        ([0.01, -0.01, 0.01, -0.01], 252, 0.18330302779823358),
        ([0.0, 0.0, 0.0], 252, 0.0),
        ([0.02, 0.02], 12, 0.0),
        ([0.01], 252, None),
        ([], 252, None),
        ([0.05, -0.03, 0.02, 0.0, -0.01], 52, 0.2175600294468),
    ],
)
def test_realized_vol(returns, periods, expected):
    out = realized_vol(returns, periods=periods)
    if expected is None:
        assert math.isnan(out)
    else:
        assert out == pytest.approx(expected, rel=1e-9)
