"""Every module-level regex is linear: CPU time per 10k-char line stays under 50 ms.

The probes are the second review's method (scratchpad c4*.py): repeat a short unit to
10,000 chars, with a few prefixes, and time ``finditer`` and ``match`` on each.
"""

import re
import time

from _diff import modify

from test_tamper_guard import diffparse, engine, rules
from test_tamper_guard.engine import analyze_diff

N = 10000
LIMIT_S = 0.05
UNITS = [" ", "\t", "'", '"', "\\'", "it.", ".a", " .", "a.", "((", "-1", "1e", "a ,", "#", "x(",
         "http://", "see ", "#1", "AB-", "skipif(", "==", "<=", "/*", "`", "_"]
WRAPS = ["%s", "x%s", "%s!", "assert %s", "expect(%s", "@pytest.mark.skipif(%s"]


def _module_regexes():
    """(name, pattern) of every compiled regex in the modules, also inside tuples and dicts."""
    out = []
    for mod in (rules, engine, diffparse):
        for name, value in vars(mod).items():
            items = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, tuple) else [("", value)]
            for key, v in items:
                if isinstance(v, re.Pattern):
                    out.append(("%s.%s%s" % (mod.__name__.rsplit(".", 1)[-1], name, "[%s]" % key if key != "" else ""), v))
    return out


def _probes():
    for u in UNITS:
        s = (u * (N // len(u) + 1))[:N]
        for w in WRAPS:
            yield w % s


def test_the_module_regex_list_is_not_empty():
    names = [n for n, _ in _module_regexes()]
    assert {"rules.TABLE_OPENER_RE", "rules._SWALLOW_RE", "rules._CHAIN_RE", "diffparse._HUNK_RE"} <= set(names)


def test_every_module_regex_is_linear_on_10k_char_lines():
    slow = []
    probes = list(_probes())
    for name, rx in _module_regexes():
        worst = 0.0
        for p in probes:
            t0 = time.process_time()
            for _ in rx.finditer(p):
                pass
            rx.match(p)
            worst = max(worst, time.process_time() - t0)
        if worst > LIMIT_S:
            slow.append((name, round(worst * 1000, 1)))
    assert slow == []


def test_table_opener_search_on_a_long_it_chain_is_fast():
    t0 = time.process_time()
    rules.TABLE_OPENER_RE.search("it." * 3333)
    assert time.process_time() - t0 < LIMIT_S


def test_swallow_match_on_a_long_tab_run_is_fast():
    t0 = time.process_time()
    rules._SWALLOW_RE.match("\t" * 10000 + "x")
    rules.is_swallow("\t" * 10000 + "x")
    assert time.process_time() - t0 < 2 * LIMIT_S


def test_100_removed_rows_under_a_10k_opener_line_are_fast():
    # Review 2 c4c: 19 s before (one TABLE_OPENER_RE scan of the opener per removed row).
    op = "it." * 3330 + "x("
    rows = "".join("  [%d, %d],\n" % (i, i) for i in range(100))
    before = "describe('d', () => {\n  " + op + "\n" + rows + "  ]);\n});\n"
    after = "describe('d', () => {\n  " + op + "\n  ]);\n});\n"
    diff = modify("test/x.test.js", before, after)
    t0 = time.process_time()
    analyze_diff(diff)
    assert time.process_time() - t0 < 1.0


def test_2000_removed_rows_below_the_opener_are_not_quadratic():
    # Each removed row used to scan back (and forward) over the whole table.
    rows = "".join("    (%d, %d),\n" % (i, i) for i in range(2000))
    before = "import pytest\n\n\n@pytest.mark.parametrize('a,b', [\n" + rows + "])\ndef test_d(a, b):\n    assert d(a) == b\n"
    after = before.replace(rows, "    (0, 0),\n")
    diff = modify("tests/test_d.py", before, after)
    t0 = time.process_time()
    fs = analyze_diff(diff)
    assert (time.process_time() - t0 < 1.0, len(fs) > 1000) == (True, True)


def test_except_assertion_error_followed_by_a_tab_line_is_fast():
    b = "def test_a():\n    try:\n        assert f() == 1\n    except AssertionError:\n" + "\t" * 9990 + "x\n"
    diff = modify("tests/test_x.py", "def test_a():\n    assert f() == 1\n", b)
    t0 = time.process_time()
    analyze_diff(diff)
    assert time.process_time() - t0 < 0.2
