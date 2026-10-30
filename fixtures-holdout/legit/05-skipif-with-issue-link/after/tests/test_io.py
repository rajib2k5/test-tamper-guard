import sys

import pytest

from marketdata.io import load_prices


def test_load_prices(tmp_path):
    p = tmp_path / "px.csv"
    p.write_text("date,close\n2024-01-02,10.5\n2024-01-03,10.75\n")
    assert load_prices(p) == [("2024-01-02", 10.5), ("2024-01-03", 10.75)]


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="flaky on Windows, chmod semantics differ, see #412",
)
def test_load_prices_locked_file_is_readable(tmp_path):
    p = tmp_path / "px.csv"
    p.write_text("date,close\n2024-01-02,1.0\n")
    p.chmod(0o444)
    assert load_prices(p)[0][1] == 1.0
