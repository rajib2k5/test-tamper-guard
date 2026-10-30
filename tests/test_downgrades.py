"""Down-grades that the second review could game (scratchpad review2/c5.py): env gates,
issue links, and expected-changed with a source change."""

import pytest

from _diff import modify

from test_tamper_guard.engine import analyze_diff


def sev(diff, rule):
    return [f.severity for f in analyze_diff(diff) if f.rule == rule]


P = "tests/test_m.py"
B = "import sys, os, shutil\nimport pytest\nfrom m import f, g\n\n\ndef test_g():\n    assert g(2) == 4\n"


def _skipif(cond):
    return sev(modify(P, B, B.replace("def test_g", "@pytest.mark.skipif(%s, reason='x')\ndef test_g" % cond)), "skip-added")


def _skip_reason(reason):
    return sev(modify(P, B, B.replace("def test_g", "@pytest.mark.skip(reason=%r)\ndef test_g" % reason)), "skip-added")


# ----------------------------------------------------------- environment gates


@pytest.mark.parametrize("cond", [
    'sys.platform != "nonexistent"', "sys.version_info > (0,)", 'True or sys.platform == "x"', "os.name",
    'shutil.which("sh")', 'not sys.platform == ""', "sys.version_info >= (3,) or True", "sys.platform",
    "condition=sys.version_info[0] > 1", "False", "sys.version_info >= (2, 7)", "sys.version_info",
    'os.name == "beos"', 'importlib.util.find_spec("yaml")', 'sys.platform.startswith("")',
    'sys.platform == "win32" or True', 'platform.system() == "Nope"', "HAS_FEATURE is None",
    "yaml.load is None", "sys.version_info < (3, 10) and not False",
])
def test_condition_that_is_not_a_real_environment_gate_stays_high(cond):
    assert _skipif(cond) == ["high"]


@pytest.mark.parametrize("cond", [
    'sys.platform == "win32"', "sys.version_info < (3, 10)", "sys.version_info[:2] >= (3, 12)",
    'sys.platform.startswith("linux")', 'sys.platform.startswith("win32")', 'sys.platform != "darwin"',
    'sys.platform == "freebsd13"', 'platform.system() == "Windows"', 'platform.system().lower() == "darwin"',
    'os.name == "nt"', 'os.name != "posix"', 'importlib.util.find_spec("yaml") is None',
    'shutil.which("git") is None', 'not shutil.which("git")', 'sys.implementation.name == "pypy"',
    'sys.version_info < (3, 9) or sys.platform == "darwin"', "(3, 11) > sys.version_info",
    "condition=sys.version_info < (3, 10)",
])
def test_condition_made_only_of_environment_probes_is_low(cond):
    assert _skipif(cond) == ["low"]


def test_multiline_unittest_skip_if_on_platform_is_low():
    b = "import sys\nimport unittest\n\n\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(f(), 1)\n"
    a = b.replace("    def test_a", '    @unittest.skipIf(\n        sys.platform == "win32",\n        "posix only",\n    )\n    def test_a')
    assert sev(modify(P, b, a), "skip-added") == ["low"]


def test_skip_unless_on_platform_is_low():
    b = "import sys\nimport unittest\n\n\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(f(), 1)\n"
    a = b.replace("    def test_a", '    @unittest.skipUnless(sys.platform.startswith("linux"), "linux")\n    def test_a')
    assert sev(modify(P, b, a), "skip-added") == ["low"]


# Review 3 (S3, scratchpad review3/gate.py): conditions that are always true (or say nothing
# about the environment) but used to down-grade to low.
@pytest.mark.parametrize("cond", [
    "sys.version_info >= (3, 0)", "sys.version_info < (4, 0)", "sys.version_info != (3, 99)",
    "sys.version_info == (3, 12)", "sys.version_info[:2] >= (3, 0)", "sys.version_info[0] >= 3",
    "sys.version_info > (3, 0, 0)", "sys.version_info[:1] < (3, 9)", "sys.version_info >= (4, 1)",
    'sys.platform != "linuxfoo"', 'sys.platform != "linux2"', 'sys.platform.startswith("lin")',
    'sys.platform.startswith("win")', 'platform.system() != "linux"', 'platform.system().lower() != "Linux"',
    "os is None", "not os is None", "not (pytest is None)", "pytest is None", "sys is not None", "True is None",
    'sys.platform != "win32" or sys.platform == "win32"',
    'not sys.platform == "win32" or not sys.platform != "win32"',
    'sys.platform.startswith("win32") or not sys.platform.startswith("win32")',
    'shutil.which("sh") is not None or not shutil.which("sh")',
    'not sys.platform.startswith("linux")', 'not sys.platform == "win32"',
])
def test_tautological_or_unproven_gate_stays_high(cond):
    assert _skipif(cond) == ["high"]


@pytest.mark.parametrize("cond", [
    "sys.version_info >= (3, 4)", 'sys.platform != "freebsd"', 'sys.platform == "openbsd7"',
    'sys.platform == "sunos5"', 'platform.system() != "Java"', 'os.name != "java"',
    'shutil.which("sh") is not None', 'importlib.util.find_spec("os") is not None',
    'not shutil.which("definitely-not-a-binary")', 'sys.platform.startswith("linux")',
    'shutil.which("git") is None or shutil.which("hg") is None',
])
def test_real_gate_from_review_3_is_low(cond):
    assert _skipif(cond) == ["low"]


@pytest.mark.parametrize("setup", ["try:\n    import yaml\nexcept ImportError:\n    yaml = None\n",
                                   "yaml = pytest.importorskip('yaml')\n"])
@pytest.mark.parametrize("cond", ["yaml is None", "yaml is not None"])
def test_none_check_on_a_name_the_diff_sets_to_none_is_low(setup, cond):
    b = B.replace("from m import f, g\n", "from m import f, g\n" + setup)
    assert sev(modify(P, b, b.replace("def test_g", "@pytest.mark.skipif(%s, reason='x')\ndef test_g" % cond)),
               "skip-added") == ["low"]


def test_none_check_on_a_name_the_diff_never_sets_to_none_stays_high():
    b = B.replace("from m import f, g\n", "from m import f, g\nimport yaml\nother = None\n")
    assert sev(modify(P, b, b.replace("def test_g", "@pytest.mark.skipif(yaml is None, reason='x')\ndef test_g")),
               "skip-added") == ["high"]


# ------------------------------------------------------------------ issue links


@pytest.mark.parametrize("reason", ["see https://x", "gh-1", "AB-1", "gh-123", "PROJ-482", "see http://example.com/x",
                                    "https://bugs.example.org/show?id=9", "see #1", "see AB-1", "https://github.com/o/r",
                                    "see https://github.com/o/r/issues/x"])
def test_reference_that_names_no_issue_stays_high(reason):
    assert _skip_reason(reason) == ["high"]


@pytest.mark.parametrize("reason", [
    "see #12", "fixes #00", "tracked in gh-123", "blocked on CORE-17", "see PROJ-482",
    "https://github.com/o/r/issues/318", "flaky: https://github.com/o/r/pull/77",
    "https://gitlab.com/g/p/-/issues/5", "https://jira.example.com/browse/PROJ-12", "issue: #42",
])
def test_reference_to_a_specific_issue_is_low(reason):
    assert _skip_reason(reason) == ["low"]


# --------------------------------------- expected-changed: which source changes count


SRC = "def g(x):\n    return x*2\n"
EXP = modify(P, B, B.replace("== 4", "== 5"))


@pytest.mark.parametrize("name,src_after", [
    ("comment", "def g(x):\n    return x*2  # perf\n"),
    ("whitespace", "def g(x):\n    return  x*2\n"),
    ("added unused fn", "def g(x):\n    return x*2\n\ndef _h():\n    pass\n"),
    ("docstring", 'def g(x):\n    """doc"""\n    return x*2\n'),
    ("multi-line docstring", 'def g(x):\n    """Double x.\n\n    More.\n    """\n    return x*2\n'),
    ("rename local var", "def g(y):\n    return y*2\n"),
])
def test_source_change_that_does_not_touch_the_tested_function_does_not_down_grade(name, src_after):
    assert sev(EXP + modify("m.py", SRC, src_after), "expected-changed") == ["medium"]


def test_real_change_to_the_function_the_test_calls_down_grades():
    assert sev(EXP + modify("m.py", SRC, "def g(x):\n    return x*2 + 1\n"), "expected-changed") == ["low"]


def test_real_change_to_another_function_of_the_module_does_not_down_grade():
    src = "def g(x):\n    return x*2\n\n\ndef other(x):\n    return x\n"
    diff = EXP + modify("m.py", src, src.replace("return x\n", "return x + 1\n"), n=1)
    assert sev(diff, "expected-changed") == ["medium"]


def test_change_inside_a_function_whose_header_is_outside_the_hunk_uses_git_section():
    # git puts the enclosing def in the hunk header (funcname); difflib does not.
    body = "".join("    y%d = x\n" % i for i in range(10))
    src_b = "def g(x):\n" + body + "    return x*2\n"
    d = modify("m.py", src_b, src_b.replace("return x*2", "return x*2 + 1"))
    head, rest = d.split("\n@@ ", 1)
    hdr, tail = rest.split("\n", 1)
    d = head + "\n@@ " + hdr + " def g(x):\n" + tail
    assert sev(EXP + d, "expected-changed") == ["low"]


def test_change_in_a_module_the_test_does_not_use_does_not_down_grade():
    assert sev(EXP + modify("other.py", "x = 1\n", "x = 2\n"), "expected-changed") == ["medium"]


def test_rename_local_with_another_real_change_down_grades():
    assert sev(EXP + modify("m.py", SRC, "def g(y):\n    return y*3\n"), "expected-changed") == ["low"]
