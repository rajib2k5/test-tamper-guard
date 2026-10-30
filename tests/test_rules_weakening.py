"""assert-weakened and test-config-weakened (docs/DESIGN.md rule table), positive and negative cases."""

import pytest

from _diff import add_file, modify

from test_tamper_guard.engine import analyze_diff


def sev(diff, rule):
    return [f.severity for f in analyze_diff(diff) if f.rule == rule]


P = "tests/test_m.py"
J = "test/m.test.js"
PYB = """import pytest
from m import f, g


def test_f():
    x = f(1)
    assert x == pytest.approx(0.5, rel=1e-6)


def test_g():
    assert g(2) == 4
"""
JSB = """import { f } from '../src/m';

test('f throws', () => {
  expect(() => f(-1)).toThrow('neg');
});

test('f val', () => {
  expect(f(1)).toEqual({ a: 1, b: 2 });
  expect(f(2)).toBeCloseTo(0.5, 5);
});
"""


def _py(old, new):
    assert old in PYB
    return sev(modify(P, PYB, PYB.replace(old, new)), "assert-weakened")


def _js(old, new):
    assert old in JSB
    return sev(modify(J, JSB, JSB.replace(old, new)), "assert-weakened")


# ----------------------------------------------------------- forms flagged when added


@pytest.mark.parametrize("new", ["assert g(2) == g(2)", "assert g(2) == 4 or True", "assert g( 2 ) == g(2), 'same'"])
def test_python_tautologies_are_flagged_medium(new):
    assert _py("assert g(2) == 4", new) == ["medium"]


def test_assert_x_equals_x_replacing_approx_is_flagged():
    assert _py("assert x == pytest.approx(0.5, rel=1e-6)", "assert x == x") == ["medium"]


def test_if_false_wrapping_an_assert_is_flagged():
    assert _py("    assert g(2) == 4\n", "    if False:\n        assert g(2) == 4\n") == ["medium"]


def test_new_test_file_with_an_x_equals_x_assert_is_not_flagged():
    # Review 2 (vitest history): new files are fixtures and matcher self-tests, not weakened tests.
    diff = add_file("tests/test_new.py", "def test_n():\n    v = n()\n    assert v == v\n")
    assert sev(diff, "assert-weakened") == []


def test_new_test_with_an_x_equals_x_assert_in_an_existing_file_is_flagged():
    new = PYB + "\n\ndef test_n():\n    v = n()\n    assert v == v\n"
    assert sev(modify(P, PYB, new), "assert-weakened") == ["medium"]


def test_js_expect_same_expression_both_sides_is_flagged():
    assert _js("expect(f(1)).toEqual({ a: 1, b: 2 })", "expect(f(1)).toEqual(f(1))") == ["medium"]


# ---------------------------------------------- forms flagged only against a stronger one


def test_assert_true_replacing_a_real_assert_is_flagged():
    assert _py("assert x == pytest.approx(0.5, rel=1e-6)", "assert True") == ["medium"]


def test_expect_true_to_be_true_replacing_a_real_expect_is_flagged():
    assert _js("expect(f(1)).toEqual({ a: 1, b: 2 })", "expect(true).toBe(true)") == ["medium"]


def test_python_early_return_as_first_statement_is_flagged():
    assert _py("def test_g():\n", "def test_g():\n    return\n") == ["medium"]


def test_js_early_return_as_first_statement_is_flagged():
    assert _js("test('f val', () => {\n", "test('f val', () => {\n  return;\n") == ["medium"]


def test_try_except_assertion_error_pass_is_flagged():
    new = "    try:\n        assert g(2) == 4\n    except AssertionError:\n        pass\n"
    assert _py("    assert g(2) == 4\n", new) == ["medium"]


@pytest.mark.parametrize("new", ["expect(f(1)).toMatchObject({ a: 1 })", "expect(f(1)).toBeDefined()",
                                 "expect(f(1)).toBeTruthy()"])
def test_exact_matcher_weakened_is_flagged(new):
    assert _js("expect(f(1)).toEqual({ a: 1, b: 2 })", new) == ["medium"]


def test_strict_equal_to_truthy_is_flagged():
    b = "test('v', () => {\n  expect(v()).toStrictEqual([1]);\n});\n"
    assert sev(modify(J, b, b.replace("toStrictEqual([1])", "toBeTruthy()")), "assert-weakened") == ["medium"]


def test_not_added_to_an_existing_expect_is_flagged():
    assert _js("expect(f(1)).toEqual", "expect(f(1)).not.toEqual") == ["medium"]


@pytest.mark.parametrize("old", ["toThrow('neg')", "toThrow(RangeError)"])
def test_to_throw_argument_dropped_is_flagged(old):
    b = JSB.replace("toThrow('neg')", old)
    assert sev(modify(J, b, b.replace(old, "toThrow()")), "assert-weakened") == ["medium"]


@pytest.mark.parametrize("broad", ["Exception", "BaseException"])
def test_pytest_raises_broadened_is_flagged(broad):
    b = "import pytest\n\n\ndef test_r():\n    with pytest.raises(ValueError):\n        f(-1)\n"
    assert sev(modify(P, b, b.replace("ValueError", broad)), "assert-weakened") == ["medium"]


@pytest.mark.parametrize("new", ["self.assertTrue(f(1))", "self.assertIsNotNone(f(1))"])
def test_assert_equal_to_assert_true_is_flagged(new):
    b = "class T:\n    def test_a(self):\n        self.assertEqual(f(1), 2)\n"
    assert sev(modify(P, b, b.replace("self.assertEqual(f(1), 2)", new)), "assert-weakened") == ["medium"]


# ------------------------------------------------------------------- not flagged


def test_new_tests_with_ordinary_asserts_are_not_flagged():
    new = PYB + "\n\ndef test_h():\n    assert h(1) == 2\n    assert h(2) or h(3)\n"
    assert sev(modify(P, PYB, new), "assert-weakened") == []


def test_extra_weak_expect_added_next_to_the_strong_one_is_not_flagged():
    assert _js("  expect(f(1)).toEqual({ a: 1, b: 2 });\n",
               "  expect(f(1)).toEqual({ a: 1, b: 2 });\n  expect(f(1)).toBeDefined();\n") == []


def test_broad_raises_in_a_new_test_is_not_flagged():
    new = PYB + "\n\ndef test_r():\n    with pytest.raises(Exception):\n        f(None)\n"
    assert sev(modify(P, PYB, new), "assert-weakened") == []


def test_matcher_strengthened_is_not_flagged():
    b = "test('v', () => {\n  expect(v()).toMatchObject({ a: 1 });\n});\n"
    assert sev(modify(J, b, b.replace("toMatchObject({ a: 1 })", "toEqual({ a: 1, b: 2 })")), "assert-weakened") == []


def test_not_removed_is_not_flagged():
    b = "test('v', () => {\n  expect(v()).not.toBe(1);\n});\n"
    assert sev(modify(J, b, b.replace(".not.toBe(1)", ".toBe(2)")), "assert-weakened") == []


def test_raises_narrowed_is_not_flagged():
    b = "import pytest\n\n\ndef test_r():\n    with pytest.raises(Exception):\n        f(-1)\n"
    assert sev(modify(P, b, b.replace("(Exception)", "(ValueError)")), "assert-weakened") == []


def test_return_at_the_end_of_a_test_or_in_a_helper_is_not_flagged():
    b = "def helper():\n    x = 1\n\n\ndef test_a():\n    assert a() == 1\n"
    a = "def helper():\n    return\n\n\ndef test_a():\n    assert a() == 1\n    return\n"
    assert sev(modify(P, b, a), "assert-weakened") == []


def test_or_true_lookalike_names_are_not_flagged():
    assert _py("assert g(2) == 4", "assert g(2) == 4 or True_value") == []


def test_tautology_in_a_non_test_file_is_not_flagged():
    diff = modify("src/m.py", "def f(x):\n    assert x == 1\n", "def f(x):\n    assert x == x\n    if False:\n        assert x\n")
    assert sev(diff, "assert-weakened") == []


def test_same_text_inside_strings_is_not_a_tautology():
    assert _py("assert g(2) == 4", "assert g('a') == g('b')") == []


# ------------------------------------------------- review 2: vitest false positives


def test_new_js_test_file_with_self_comparisons_is_not_flagged():
    diff = add_file("test/fixtures/first.test.ts", "test('a', () => {\n  expect(1).toBe(1);\n  expect(x).toBe(x);\n});\n")
    assert sev(diff, "assert-weakened") == []


@pytest.mark.parametrize("new", [
    "expect(Uint8Array.from([1, 2, 3])).toEqual(Uint8Array.from([1, 2, 3]))",
    "expect(new Set([1])).toEqual(new Set([1]))",
    "expect([1, 2]).toEqual([1, 2])",
    "expect({ a: 1 }).toStrictEqual({ a: 1 })",
])
def test_matcher_self_test_on_a_constructed_value_is_not_flagged(new):
    assert _js("expect(f(1)).toEqual({ a: 1, b: 2 })", new) == []


@pytest.mark.parametrize("new", ["assert [1, 2] == [1, 2]", "assert {'a': 1} == {'a': 1}", "assert Point(*[1, 2]) == Point(*[1, 2])"])
def test_python_self_comparison_of_a_constructed_value_is_not_flagged(new):
    assert _py("assert g(2) == 4", new) == []


@pytest.mark.parametrize("new", ["expect(f(1)).toEqual(f(1))", "expect(res.body.id).toBe(res.body.id)", "expect(x).toBe(x)"])
def test_js_self_comparison_of_a_name_or_call_is_still_flagged(new):
    assert _js("expect(f(1)).toEqual({ a: 1, b: 2 })", new) == ["medium"]


def test_expect_text_inside_a_fixture_string_is_not_a_self_comparison():
    new = "const files = { 'a.test.ts': \"test('x', () => { expect(1).toBe(1) })\" };\n  expect(f(1)).toEqual({ a: 1, b: 2 })"
    assert _js("expect(f(1)).toEqual({ a: 1, b: 2 })", new) == []


def test_expect_text_inside_a_multi_line_template_fixture_is_not_a_self_comparison():
    new = "const src = `\n    test('x', () => {\n      expect(1).toBe(1)\n      expect(y).toBe(y)\n    })\n  `;\n  expect(f(1)).toEqual({ a: 1, b: 2 })"
    assert _js("expect(f(1)).toEqual({ a: 1, b: 2 })", new) == []


def test_not_added_on_a_different_subject_is_not_a_weakening():
    assert _js("expect(f(1)).toEqual({ a: 1, b: 2 })", "expect(g(1)).not.toEqual({ a: 1, b: 2 })") == []


def test_not_added_with_a_different_matcher_is_not_a_weakening():
    assert _js("expect(f(1)).toEqual({ a: 1, b: 2 })", "expect(f(1)).not.toContain('x')") == []


def test_not_added_with_the_same_subject_and_matcher_is_flagged():
    assert _js("expect(f(1)).toEqual({ a: 1, b: 2 })", "expect(f(1)).not.toEqual({ a: 3 })") == ["medium"]


# ---------------------------------------------------------- test-config-weakened


def cfg(path, before, after):
    return sev(modify(path, before, after), "test-config-weakened")


@pytest.mark.parametrize("path,before,after", [
    ("pytest.ini", "[pytest]\naddopts = -q\n", "[pytest]\naddopts = -q --deselect tests/test_m.py::test_g\n"),
    ("pyproject.toml", '[tool.pytest.ini_options]\naddopts = "-q"\n', "[tool.pytest.ini_options]\naddopts = \"-q -k 'not test_g'\"\n"),
    ("pyproject.toml", '[tool.pytest.ini_options]\naddopts = "-q"\n', '[tool.pytest.ini_options]\naddopts = "-q --ignore=tests/test_m.py"\n'),
    ("setup.cfg", "[tool:pytest]\naddopts = -q\n", "[tool:pytest]\naddopts = -q --ignore-glob=tests/test_slow*\n"),
    ("tox.ini", "[pytest]\naddopts =\n    -q\n", "[pytest]\naddopts =\n    -q\n    --deselect tests/test_m.py::test_g\n"),
    ("pyproject.toml", '[tool.pytest.ini_options]\naddopts = [\n  "-q",\n]\n',
     '[tool.pytest.ini_options]\naddopts = [\n  "-q",\n  "-k", "not slow",\n]\n'),
])
def test_pytest_addopts_that_drop_tests_are_flagged_high(path, before, after):
    assert cfg(path, before, after) == ["high"]


@pytest.mark.parametrize("after", [
    "import pytest\n\ncollect_ignore = ['test_m.py']\n",
    "import pytest\n\ncollect_ignore_glob = ['test_slow_*.py']\n",
    "import pytest\n\n\ndef pytest_collection_modifyitems(items):\n    items[:] = [i for i in items if 'g' not in i.name]\n",
    ("import pytest\n\n\ndef pytest_collection_modifyitems(config, items):\n    for item in list(items):\n"
     "        if 'g' in item.name:\n            items.remove(item)\n"),
    ("import pytest\n\n\ndef pytest_collection_modifyitems(config, items):\n    bad = [i for i in items if i.name == 'test_g']\n"
     "    config.hook.pytest_deselected(items=bad)\n"),
])
def test_conftest_that_drops_tests_is_flagged_high(after):
    assert cfg("tests/conftest.py", "import pytest\n", after) == ["high"]


@pytest.mark.parametrize("path,before,after", [
    ("jest.config.js", "module.exports = {\n  testEnvironment: 'node',\n};\n",
     "module.exports = {\n  testEnvironment: 'node',\n  testPathIgnorePatterns: ['m.test.js'],\n};\n"),
    ("package.json", '{\n  "jest": {\n    "testEnvironment": "node"\n  }\n}\n',
     '{\n  "jest": {\n    "testEnvironment": "node",\n    "testPathIgnorePatterns": ["m.test.js"]\n  }\n}\n'),
    ("jest.config.ts", "export default {\n  modulePathIgnorePatterns: [\n    '<rootDir>/dist/',\n  ],\n};\n",
     "export default {\n  modulePathIgnorePatterns: [\n    '<rootDir>/dist/',\n    '<rootDir>/src/m',\n  ],\n};\n"),
    ("package.json", '{\n  "scripts": {\n    "test": "jest"\n  }\n}\n', '{\n  "scripts": {\n    "test": "jest || true"\n  }\n}\n'),
    ("package.json", '{\n  "scripts": {\n    "test": "jest"\n  }\n}\n', '{\n  "scripts": {\n    "test": "jest --passWithNoTests"\n  }\n}\n'),
])
def test_jest_config_that_drops_tests_is_flagged_high(path, before, after):
    assert cfg(path, before, after) == ["high"]


@pytest.mark.parametrize("path,before,after", [
    ("pytest.ini", "[pytest]\naddopts = -q\n", "[pytest]\naddopts = -v --strict-markers\n"),
    ("pytest.ini", "[pytest]\naddopts = -q -k 'not slow'\n", "[pytest]\naddopts = -q\n"),
    ("pytest.ini", "[pytest]\naddopts = -q -k 'not slow'\n", "[pytest]\naddopts = -q -k 'not slow' -ra\n"),
    ("pyproject.toml", "[tool.ruff]\nline-length = 100\n", '[tool.ruff]\nline-length = 100\nignore = ["E501"]\n'),
    ("tests/conftest.py", "import pytest\n", "import pytest\n\n\n@pytest.fixture\ndef db():\n    return {}\n"),
    ("tests/conftest.py", "import pytest\n", ("import pytest\n\n\ndef pytest_collection_modifyitems(items):\n"
                                               "    for item in items:\n        item.add_marker(pytest.mark.slow)\n")),
    ("package.json", '{\n  "scripts": {\n    "test": "jest",\n    "lint": "eslint ."\n  }\n}\n',
     '{\n  "scripts": {\n    "test": "jest --coverage",\n    "lint": "eslint . || true"\n  }\n}\n'),
    ("jest.config.js", "module.exports = {\n  testEnvironment: 'node',\n};\n",
     "module.exports = {\n  testEnvironment: 'jsdom',\n  testPathIgnorePatterns: ['/node_modules/'],\n};\n"),
    ("src/settings.py", "X = 1\n", "collect_ignore = ['a']\n"),
])
def test_config_changes_that_keep_tests_are_not_flagged(path, before, after):
    assert cfg(path, before, after) == []
