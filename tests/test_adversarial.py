"""Untrusted-input behaviour: size, time and malformed diffs never crash."""

import random
import time

from _diff import modify

from test_tamper_guard.engine import analyze_diff


def _big_test_diff(n_lines):
    """A test-file diff with n_lines change lines mixing every rule's trigger."""
    chunk = [
        "-def test_a%d():\n", "-    assert f(1) == 2\n", "+def test_b%d():\n", "+    assert f(1) == 3\n",
        "+@pytest.mark.skip\n", "-    x = approx(1, rel=1e-6)\n", "+    x = approx(1, rel=1e-1)\n",
        "+    # assert f(1) == 2\n", " ctx\n",
    ]
    body = []
    i = 0
    while len(body) < n_lines:
        body.extend(c % i if "%d" in c else c for c in chunk)
        i += 1
    old = sum(1 for b in body if b[0] in "- ")
    new = sum(1 for b in body if b[0] in "+ ")
    return "--- a/tests/test_big.py\n+++ b/tests/test_big.py\n@@ -1,%d +1,%d @@\n%s" % (old, new, "".join(body))


def test_20000_char_line_is_analysed_without_error():
    long = "x" * 20000
    diff = modify("tests/test_a.py", "def test_a():\n    assert f() == '%s'\n" % long,
                  "def test_a():\n    assert f() == '%sy'\n" % long)
    assert isinstance(analyze_diff(diff), list)


def test_50k_line_diff_runs_in_linear_time():
    # ~0.7 s CPU locally, ~2.1 s on a GitHub runner. The bound catches the quadratic
    # regressions seen in review (18-160 s), not runner speed.
    diff = _big_test_diff(50000)
    t0 = time.process_time()
    findings = analyze_diff(diff)
    elapsed = time.process_time() - t0
    assert (elapsed < 6.0, len(findings) > 0) == (True, True), elapsed


def test_5k_line_diff_runs_under_the_hook_budget_of_one_second():
    diff = _big_test_diff(5000)
    t0 = time.process_time()
    analyze_diff(diff)
    assert time.process_time() - t0 < 1.0


def test_pathological_regex_inputs_finish_fast():
    nasty = [
        '"' + "\\" * 5000, "'" * 5000, "(" * 5000, ")" * 5000, "." * 5000, "it" + ".x" * 3000 + " ",
        "approx(" + "1," * 3000, "abs(" + "(" * 3000 + "<", "#" * 5000 + "1", "a-" * 3000,
        "expect(" * 2000, "1e" * 3000, "_" * 5000, "it.skip" * 1000, "/*" * 3000,
    ]
    before = "def test_a():\n" + "".join("    x = %r\n" % i for i in range(len(nasty)))
    after = "def test_a():\n" + "".join("    %s\n" % s for s in nasty)
    diff = modify("tests/test_a.py", before, after) + modify("src/a.test.js", before, after)
    t0 = time.process_time()
    analyze_diff(diff)
    assert time.process_time() - t0 < 2.0


def test_malformed_headers_do_not_crash():
    samples = [
        "diff --git\n", "diff --git a/x\n@@ -1 +1 @@\n-a\n+b\n", "--- \n+++ \n@@ -x +y @@\n",
        "@@ -1,2 +1,2 @@\n-a\n+b\n", 'diff --git "a/unterminated b/x\n', "+++ b/only\n@@ -1 +1 @@\n+a\n",
        "--- a/t.py\n+++ b/t.py\n@@ -1,99999999999 +1,1 @@\n-a\n", "rename from x\nrename to y\n",
        "diff --git a/t.py b/t.py\nBinary files a/t.py and b/t.py differ\n@@ -1 +1 @@\n-a\n+b\n",
        "\x00\x01\x02", "--- a/t.py\n+++ b/t.py\n@@ -0,0 +1 @@\n+" + "\udcff" + "\n",
        'diff --git "a/\\777\\x" "b/\\1"\n--- "a/\\777\\x"\n+++ "b/\\1"\n@@ -1 +1 @@\n-a\n+b\n',
    ]
    assert all(isinstance(analyze_diff(s), list) for s in samples)


def test_random_mutations_of_a_real_diff_do_not_crash():
    base = list(_big_test_diff(200) + modify("src/x.test.js", "it('a', () => {\n  expect(1).toBe(1);\n});\n",
                                             "it.only('a', () => {\n  expect(1).toBeCloseTo(1, 0);\n});\n"))
    rng = random.Random(1234)
    alphabet = "-+ @\\\n\"'`()[]{}#/*.,=:0123456789abcdefitxp"
    for _ in range(300):
        s = base[:]
        for _ in range(rng.randint(1, 40)):
            s[rng.randrange(len(s))] = rng.choice(alphabet)
        analyze_diff("".join(s))


def _paired(lines_old, lines_new, path="tests/test_r.py"):
    hunks = "".join("@@ -%d,1 +%d,1 @@\n-%s\n+%s\n" % (i + 1, i + 1, o, n)
                    for i, (o, n) in enumerate(zip(lines_old, lines_new)))
    return "diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n%s" % (path, path, path, path, hunks)


def test_keyword_argument_padded_with_whitespace_is_linear():
    # 50 paired lines of `rel=<n><~10k spaces/tabs>y)`: the old `\s*(.*?)\s*$` took ~20 s.
    pad = " \t" * 4900
    diff = _paired(["    assert x == pytest.approx(1, rel=2%sy%d)" % (pad, i) for i in range(50)],
                   ["    assert x == pytest.approx(1, rel=1%sy%d)" % (pad, i) for i in range(50)])
    t0 = time.process_time()
    analyze_diff(diff)
    assert time.process_time() - t0 < 1.0


def test_unterminated_strings_full_of_escaped_quotes_are_linear():
    # Every quote of an unterminated '\'\'\'... run used to start a scan to the end of the line.
    for body in ("\\'" * 4900, "\\'" * 4900 + "\\", '\\"' * 4900, "\\`" * 4900):
        q = body[1]
        olds = ["    assert f(%d) == 1" % i for i in range(50)]
        news = ["    assert f(%d) == %s%s" % (i, q, body) for i in range(50)]
        t0 = time.process_time()
        analyze_diff(_paired(olds, news) + _paired(olds, news, "test/r.test.js"))
        assert time.process_time() - t0 < 1.0, repr(body[:4])
