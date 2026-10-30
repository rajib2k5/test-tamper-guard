"""Behaviour of each rule from docs/DESIGN.md, positive and negative cases."""

import pytest

from _diff import add_file, delete_file, modify

from test_tamper_guard.engine import analyze_diff


def sev(diff, rule):
    """Severities of the findings for ``rule``, in order."""
    return [f.severity for f in analyze_diff(diff) if f.rule == rule]


def only(diff, rule):
    return [f for f in analyze_diff(diff) if f.rule == rule]


PY_TWO_TESTS = """
    from calc import add, sub


    def test_add():
        assert add(1, 2) == 3


    def test_sub():
        assert sub(3, 1) == 2
"""

PY_ONE_TEST = """
    from calc import add, sub


    def test_add():
        assert add(1, 2) == 3
"""

# ---------------------------------------------------------------- test-deleted


def test_removed_pytest_function_is_flagged_high():
    assert sev(modify("tests/test_calc.py", PY_TWO_TESTS, PY_ONE_TEST), "test-deleted") == ["high"]


def test_removed_test_finding_points_at_old_def_line():
    (f,) = only(modify("tests/test_calc.py", PY_TWO_TESTS, PY_ONE_TEST), "test-deleted")
    assert (f.path, f.line, "test_sub" in f.message) == ("tests/test_calc.py", 8, True)


JS_TWO = """
    import { add, sub } from '../src/calc';

    describe('calc', () => {
      it('adds', () => {
        expect(add(1, 2)).toBe(3);
      });

      it('subtracts', () => {
        expect(sub(3, 1)).toBe(2);
      });
    });
"""

JS_ONE = """
    import { add, sub } from '../src/calc';

    describe('calc', () => {
      it('adds', () => {
        expect(add(1, 2)).toBe(3);
      });
    });
"""


def test_removed_jest_it_block_is_flagged_high():
    assert sev(modify("src/calc.test.js", JS_TWO, JS_ONE), "test-deleted") == ["high"]


def test_removed_jest_test_with_name_on_next_line_is_flagged():
    before = """
        test('keeps', () => {
          expect(1 + 1).toBe(2);
        });

        test(
          'handles a very long description that wraps',
          () => {
            expect(parse('x')).toEqual(['x']);
          },
        );
    """
    after = """
        test('keeps', () => {
          expect(1 + 1).toBe(2);
        });
    """
    (f,) = only(modify("src/parse.test.ts", before, after), "test-deleted")
    assert "handles a very long description" in f.message


def test_deleted_pytest_file_is_flagged_high():
    assert sev(delete_file("tests/test_calc.py", PY_TWO_TESTS), "test-deleted") == ["high"]


def test_deleted_jest_file_is_flagged_high():
    assert sev(delete_file("src/__tests__/calc.js", JS_TWO), "test-deleted") == ["high"]


def test_test_moved_to_another_file_is_not_flagged():
    diff = modify("tests/test_calc.py", PY_TWO_TESTS, PY_ONE_TEST) + add_file(
        "tests/test_sub.py", "from calc import sub\n\n\ndef test_sub():\n    assert sub(3, 1) == 2\n"
    )
    assert sev(diff, "test-deleted") == []


def test_renamed_test_with_unchanged_body_is_not_flagged():
    after = PY_TWO_TESTS.replace("def test_sub():", "def test_sub_returns_difference():")
    assert sev(modify("tests/test_calc.py", PY_TWO_TESTS, after), "test-deleted") == []


def test_test_replaced_by_a_different_test_is_flagged():
    after = PY_TWO_TESTS.replace(
        "def test_sub():\n        assert sub(3, 1) == 2",
        "def test_import():\n        import calc",
    )
    diff = modify("tests/test_calc.py", PY_TWO_TESTS, after)
    # Replaced in the same place: a rename/rewrite (low), but the lost assert is still medium.
    assert (sev(diff, "test-deleted"), sev(diff, "assert-removed")) == (["low"], ["medium"])


def test_removed_test_of_removed_feature_is_down_graded_to_low():
    src_before = "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n"
    src_after = "def add(a, b):\n    return a + b\n"
    diff = modify("tests/test_calc.py", PY_TWO_TESTS, PY_ONE_TEST) + modify("src/calc.py", src_before, src_after)
    assert sev(diff, "test-deleted") == ["low"]


def test_removed_jest_test_of_removed_feature_is_down_graded_to_low():
    src_before = "export function add(a, b) {\n  return a + b;\n}\n\nexport function sub(a, b) {\n  return a - b;\n}\n"
    src_after = "export function add(a, b) {\n  return a + b;\n}\n"
    diff = modify("src/calc.test.js", JS_TWO, JS_ONE) + modify("src/calc.js", src_before, src_after)
    assert sev(diff, "test-deleted") == ["low"]


def test_feature_moved_not_removed_keeps_high():
    src_before = "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n"
    src_after = "def add(a, b):\n    return a + b\n"
    diff = (
        modify("tests/test_calc.py", PY_TWO_TESTS, PY_ONE_TEST)
        + modify("src/calc.py", src_before, src_after)
        + add_file("src/ops.py", "def sub(a, b):\n    return a - b\n")
    )
    assert sev(diff, "test-deleted") == ["high"]


def test_def_test_removed_from_non_test_file_is_not_flagged():
    before = "def test_connection():\n    return True\n\n\ndef other():\n    pass\n"
    after = "def other():\n    pass\n"
    assert sev(modify("src/db.py", before, after), "test-deleted") == []


# ----------------------------------------------------------------- skip-added

PY_BASE = """
    import pytest


    def test_parse():
        assert parse("1") == 1
"""


def _py_with(line):
    return PY_BASE.replace("    def test_parse", "    %s\n    def test_parse" % line)


def test_pytest_mark_skip_is_flagged_high():
    assert sev(modify("tests/test_p.py", PY_BASE, _py_with('@pytest.mark.skip(reason="flaky")')), "skip-added") == ["high"]


def test_pytest_mark_skipif_is_flagged():
    assert sev(modify("tests/test_p.py", PY_BASE, _py_with("@pytest.mark.skipif(True, reason='x')")), "skip-added") == ["high"]


def test_pytest_mark_xfail_is_flagged():
    assert sev(modify("tests/test_p.py", PY_BASE, _py_with("@pytest.mark.xfail")), "skip-added") == ["high"]


def test_unittest_skip_decorator_is_flagged():
    assert sev(modify("tests/test_p.py", PY_BASE, _py_with('@unittest.skip("broken")')), "skip-added") == ["high"]


def test_pytest_skip_call_in_body_is_flagged():
    after = PY_BASE.replace('assert parse("1") == 1', 'pytest.skip("todo")\n        assert parse("1") == 1')
    assert sev(modify("tests/test_p.py", PY_BASE, after), "skip-added") == ["high"]


def test_self_skiptest_call_is_flagged():
    after = PY_BASE.replace('assert parse("1") == 1', 'self.skipTest("later")\n        assert parse("1") == 1')
    assert sev(modify("tests/test_p.py", PY_BASE, after), "skip-added") == ["high"]


def test_module_level_pytestmark_skip_is_flagged():
    after = PY_BASE.replace("import pytest\n", "import pytest\n\n    pytestmark = pytest.mark.skip\n")
    assert sev(modify("tests/test_p.py", PY_BASE, after), "skip-added") == ["high"]


JS_BASE = """
    describe('parse', () => {
      it('reads ints', () => {
        expect(parse('1')).toBe(1);
      });
    });
"""


def _js_skip(old, new):
    return sev(modify("src/parse.test.js", JS_BASE, JS_BASE.replace(old, new)), "skip-added")


def test_it_skip_is_flagged_high():
    assert _js_skip("it('reads", "it.skip('reads") == ["high"]


def test_xit_is_flagged():
    assert _js_skip("it('reads", "xit('reads") == ["high"]


def test_xdescribe_is_flagged():
    assert _js_skip("describe('parse'", "xdescribe('parse'") == ["high"]


def test_describe_skip_is_flagged():
    assert _js_skip("describe('parse'", "describe.skip('parse'") == ["high"]


def test_it_only_focus_is_flagged():
    assert _js_skip("it('reads", "it.only('reads") == ["high"]


def test_fit_focus_is_flagged():
    assert _js_skip("it('reads", "fit('reads") == ["high"]


def test_fdescribe_focus_is_flagged():
    assert _js_skip("describe('parse'", "fdescribe('parse'") == ["high"]


def test_it_failing_is_flagged():
    assert _js_skip("it('reads", "it.failing('reads") == ["high"]


def test_test_todo_is_flagged():
    before = "test('adds', () => {\n  expect(add(1, 2)).toBe(3);\n});\n"
    after = "test.todo('adds');\n"
    assert sev(modify("src/add.test.js", before, after), "skip-added") == ["high"]


def test_skip_with_issue_number_is_down_graded_to_low():
    assert sev(modify("tests/test_p.py", PY_BASE, _py_with('@pytest.mark.skip(reason="see #123")')), "skip-added") == ["low"]


def test_skip_with_issue_url_is_down_graded_to_low():
    line = '@pytest.mark.skip(reason="https://github.com/o/r/issues/9")'
    assert sev(modify("tests/test_p.py", PY_BASE, _py_with(line)), "skip-added") == ["low"]


def test_skip_with_jira_key_after_a_tracker_word_is_down_graded_to_low():
    assert _js_skip("it('reads", "it.skip('reads (see PROJ-482)") == ["low"]


def test_skip_with_issue_link_on_continuation_line_is_down_graded():
    line = "@pytest.mark.skip(\n        reason=\"blocked by #77\",\n    )"
    assert sev(modify("tests/test_p.py", PY_BASE, _py_with(line)), "skip-added") == ["low"]


def test_model_fit_call_is_not_a_focus_marker():
    after = PY_BASE.replace('assert parse("1") == 1', 'model.fit(x)\n        assert parse("1") == 1')
    after_js = JS_BASE.replace("expect(parse('1')).toBe(1);", "model.fit(x);\n    expect(parse('1')).toBe(1);")
    assert sev(modify("tests/test_p.py", PY_BASE, after), "skip-added") + sev(
        modify("src/parse.test.js", JS_BASE, after_js), "skip-added") == []


def test_existing_skip_with_changed_reason_is_not_flagged():
    before = _py_with('@pytest.mark.skip(reason="flaky")')
    after = _py_with('@pytest.mark.skip(reason="flaky on CI")')
    assert sev(modify("tests/test_p.py", before, after), "skip-added") == []


def test_skip_text_in_non_test_file_is_not_flagged():
    diff = modify("src/runner.py", "def run():\n    pass\n", "def run():\n    pytest.skip('x')\n")
    assert sev(diff, "skip-added") == []


# ---------------------------------------------------------- tolerance-loosened


def _tol(path, before, after):
    return sev(modify(path, before, after), "tolerance-loosened")


def test_approx_rel_increase_is_flagged_high():
    b = "def test_v():\n    assert v() == pytest.approx(1.5, rel=1e-6)\n"
    assert _tol("tests/test_v.py", b, b.replace("rel=1e-6", "rel=0.1")) == ["high"]


def test_approx_abs_increase_split_over_lines_is_flagged():
    b = "def test_v():\n    assert v() == pytest.approx(\n        1.5,\n        abs=1e-9,\n    )\n"
    assert _tol("tests/test_v.py", b, b.replace("abs=1e-9", "abs=0.5")) == ["high"]


def test_approx_tolerance_added_where_none_was_is_flagged():
    b = "def test_v():\n    assert v() == pytest.approx(1.5)\n"
    assert _tol("tests/test_v.py", b, b.replace("approx(1.5)", "approx(1.5, abs=0.2)")) == ["high"]


def test_unittest_places_lowered_is_flagged():
    b = "class T(TestCase):\n    def test_v(self):\n        self.assertAlmostEqual(v(), 1.5, places=7)\n"
    assert _tol("tests/test_v.py", b, b.replace("places=7", "places=1")) == ["high"]


def test_unittest_delta_increase_is_flagged():
    b = "class T(TestCase):\n    def test_v(self):\n        self.assertAlmostEqual(v(), 1.5, delta=0.01)\n"
    assert _tol("tests/test_v.py", b, b.replace("delta=0.01", "delta=1")) == ["high"]


def test_numpy_assert_allclose_rtol_increase_is_flagged():
    b = "def test_v():\n    np.testing.assert_allclose(v(), [1.0, 2.0], rtol=1e-7)\n"
    assert _tol("tests/test_v.py", b, b.replace("rtol=1e-7", "rtol=1e-2")) == ["high"]


def test_numpy_decimal_lowered_is_flagged():
    b = "def test_v():\n    np.testing.assert_almost_equal(v(), 1.5, decimal=6)\n"
    assert _tol("tests/test_v.py", b, b.replace("decimal=6", "decimal=2")) == ["high"]


def test_abs_difference_bound_widened_is_flagged():
    b = "def test_v():\n    assert abs(v() - 1.5) < 1e-6\n"
    assert _tol("tests/test_v.py", b, b.replace("1e-6", "0.5")) == ["high"]


def test_to_be_close_to_digits_lowered_is_flagged():
    b = "it('v', () => {\n  expect(v()).toBeCloseTo(0.3, 5);\n});\n"
    assert _tol("src/v.test.js", b, b.replace("0.3, 5)", "0.3, 1)")) == ["high"]


def test_to_be_close_to_digits_dropped_to_default_is_flagged():
    b = "it('v', () => {\n  expect(v()).toBeCloseTo(0.3, 5);\n});\n"
    assert _tol("src/v.test.js", b, b.replace("0.3, 5)", "0.3)")) == ["high"]


def test_to_be_close_to_digits_lowered_over_lines_is_flagged():
    b = "it('v', () => {\n  expect(v()).toBeCloseTo(\n    3.14159,\n    5,\n  );\n});\n"
    assert _tol("src/v.test.js", b, b.replace("    5,", "    1,")) == ["high"]


def test_exact_equality_made_approximate_is_flagged():
    b = "def test_v():\n    assert total() == 10.5\n"
    assert _tol("tests/test_v.py", b, b.replace("== 10.5", "== pytest.approx(10.5, rel=0.05)")) == ["high"]


def test_assert_equal_made_almost_equal_is_flagged():
    b = "class T(TestCase):\n    def test_v(self):\n        self.assertEqual(v(), 1.5)\n"
    assert _tol("tests/test_v.py", b, b.replace("assertEqual(v(), 1.5)", "assertAlmostEqual(v(), 1.5, places=1)")) == ["high"]


def test_to_be_made_to_be_close_to_is_flagged():
    b = "it('v', () => {\n  expect(v()).toBe(42);\n});\n"
    assert _tol("src/v.test.js", b, b.replace("toBe(42)", "toBeCloseTo(42, 0)")) == ["high"]


def test_tightened_approx_is_not_flagged_by_any_rule():
    b = "def test_v():\n    assert v() == pytest.approx(1.5, rel=1e-2)\n"
    assert analyze_diff(modify("tests/test_v.py", b, b.replace("rel=1e-2", "rel=1e-9"))) == []


def test_tightened_to_be_close_to_is_not_flagged_by_any_rule():
    b = "it('v', () => {\n  expect(v()).toBeCloseTo(0.3, 2);\n});\n"
    assert analyze_diff(modify("src/v.test.js", b, b.replace("0.3, 2)", "0.3, 8)"))) == []


def test_tolerance_change_in_non_test_file_is_not_flagged():
    b = "def close(a, b):\n    return math.isclose(a, b, rel_tol=1e-9)\n"
    assert _tol("src/num.py", b, b.replace("1e-9", "1e-2")) == []


# ------------------------------------------------------------ expected-changed


def _exp(path, before, after):
    return sev(modify(path, before, after), "expected-changed")


def test_changed_number_in_pytest_assert_is_flagged_medium():
    b = "def test_add():\n    assert add(2, 2) == 4\n"
    assert _exp("tests/test_a.py", b, b.replace("== 4", "== 5")) == ["medium"]


def test_changed_string_in_pytest_assert_is_flagged():
    b = 'def test_slug():\n    assert slugify("Hello World") == "hello-world"\n'
    assert _exp("tests/test_a.py", b, b.replace('"hello-world"', '"hello world"')) == ["medium"]


def test_changed_negative_number_is_flagged():
    b = "def test_add():\n    assert add(2, -3) == -1\n"
    assert _exp("tests/test_a.py", b, b.replace("== -1", "== 1")) == ["medium"]


def test_changed_bool_in_jest_expect_is_flagged():
    b = "it('valid', () => {\n  expect(isValid('x')).toBe(true);\n});\n"
    assert _exp("src/v.test.js", b, b.replace("toBe(true)", "toBe(false)")) == ["medium"]


def test_changed_value_inside_multiline_to_equal_is_flagged():
    b = "it('obj', () => {\n  expect(build()).toEqual({\n    a: 1,\n    b: 2,\n  });\n});\n"
    assert _exp("src/v.test.js", b, b.replace("b: 2,", "b: 3,")) == ["medium"]


def test_changed_value_inside_multiline_pytest_assert_is_flagged():
    b = 'def test_obj():\n    assert build() == {\n        "a": 1,\n        "b": 2,\n    }\n'
    assert _exp("tests/test_a.py", b, b.replace('"b": 2', '"b": 3')) == ["medium"]


def test_changed_expected_variable_is_flagged():
    b = "def test_total():\n    expected = 42\n    assert total() == expected\n"
    assert _exp("tests/test_a.py", b, b.replace("= 42", "= 41")) == ["medium"]


def test_changed_unittest_assert_equal_value_is_flagged():
    b = "class T(TestCase):\n    def test_v(self):\n        self.assertEqual(count(), 3)\n"
    assert _exp("tests/test_a.py", b, b.replace("count(), 3", "count(), 4")) == ["medium"]


def test_expected_change_with_source_change_is_down_graded_to_low():
    b = "import calc\n\n\ndef test_add():\n    assert calc.add(2, 2) == 4\n"
    diff = modify("tests/test_a.py", b, b.replace("== 4", "== 5")) + modify(
        "src/calc.py", "def add(a, b):\n    return a + b\n", "def add(a, b):\n    return a + b + 1\n")
    assert sev(diff, "expected-changed") == ["low"]


def test_quote_style_change_is_not_flagged():
    b = "def test_slug():\n    assert slugify('a b') == 'a-b'\n"
    assert analyze_diff(modify("tests/test_a.py", b, b.replace("'", '"'))) == []


def test_number_respelled_with_same_value_is_not_flagged():
    b = "def test_v():\n    assert v() == 1.0\n"
    assert _exp("tests/test_a.py", b, b.replace("1.0", "1.00")) == []


def test_changed_call_target_is_not_an_expected_change():
    b = "def test_v():\n    assert parse(x) == 3\n"
    assert _exp("tests/test_a.py", b, b.replace("parse(x)", "parse_int(x)")) == []


def test_changed_literal_outside_an_assertion_is_not_flagged():
    b = "def test_v():\n    data = load(1)\n    assert check(data)\n"
    assert _exp("tests/test_a.py", b, b.replace("load(1)", "load(2)")) == []


def test_changed_literal_in_non_test_file_is_not_flagged():
    b = "def f():\n    assert x == 1\n"
    assert _exp("src/a.py", b, b.replace("== 1", "== 2")) == []


# -------------------------------------------------------------- assert-removed


def test_net_loss_of_pytest_asserts_is_flagged_medium():
    b = "def test_v():\n    r = v()\n    assert r.ok\n    assert r.code == 200\n    assert r.body\n"
    a = "def test_v():\n    r = v()\n    assert r.ok\n"
    assert sev(modify("tests/test_a.py", b, a), "assert-removed") == ["medium"]


def test_net_loss_of_jest_expects_is_flagged():
    b = "it('v', () => {\n  const r = v();\n  expect(r.ok).toBe(true);\n  expect(r.code).toBe(200);\n});\n"
    a = "it('v', () => {\n  const r = v();\n  expect(r.ok).toBe(true);\n});\n"
    assert sev(modify("src/v.test.js", b, a), "assert-removed") == ["medium"]


def test_assert_replaced_by_assert_true_is_flagged():
    b = "def test_v():\n    assert v() == 3\n"
    assert sev(modify("tests/test_a.py", b, b.replace("assert v() == 3", "assert True")), "assert-removed") == ["medium"]


def test_assert_replaced_by_pass_is_flagged():
    b = "def test_v():\n    assert v() == 3\n"
    assert sev(modify("tests/test_a.py", b, b.replace("assert v() == 3", "pass")), "assert-removed") == ["medium"]


def test_expect_replaced_by_tautology_is_flagged():
    b = "it('v', () => {\n  expect(v()).toBe(3);\n});\n"
    assert sev(modify("src/v.test.js", b, b.replace("expect(v()).toBe(3)", "expect(true).toBe(true)")), "assert-removed") == ["medium"]


def test_reordered_asserts_are_not_flagged():
    b = "def test_v():\n    assert a()\n    x = 1\n    assert b()\n"
    a = "def test_v():\n    assert b()\n    x = 1\n    assert a()\n"
    assert sev(modify("tests/test_a.py", b, a), "assert-removed") == []


def test_asserts_inside_a_deleted_test_are_left_to_test_deleted():
    assert sev(modify("tests/test_calc.py", PY_TWO_TESTS, PY_ONE_TEST), "assert-removed") == []


def test_assert_removed_from_non_test_file_is_not_flagged():
    b = "def f(x):\n    assert x\n    return x\n"
    assert sev(modify("src/a.py", b, b.replace("    assert x\n", "")), "assert-removed") == []


# ---------------------------------------------------------- test-commented-out


def test_pytest_test_commented_out_is_flagged_high():
    a = PY_TWO_TESTS.replace(
        "def test_sub():\n        assert sub(3, 1) == 2",
        "# def test_sub():\n    #     assert sub(3, 1) == 2",
    )
    assert sev(modify("tests/test_calc.py", PY_TWO_TESTS, a), "test-commented-out") == ["high"]


def test_single_assert_commented_out_is_flagged():
    b = "def test_v():\n    assert v() == 3\n    assert w()\n"
    assert sev(modify("tests/test_a.py", b, b.replace("    assert v() == 3", "    # assert v() == 3")), "test-commented-out") == ["high"]


def test_jest_it_block_commented_with_line_comments_is_flagged():
    a = JS_TWO.replace(
        "  it('subtracts', () => {\n        expect(sub(3, 1)).toBe(2);\n      });",
        "  // it('subtracts', () => {\n      //   expect(sub(3, 1)).toBe(2);\n      // });",
    )
    assert sev(modify("src/calc.test.js", JS_TWO, a), "test-commented-out") == ["high"]


def test_jest_it_block_wrapped_in_block_comment_is_flagged():
    a = JS_TWO.replace(
        "  it('subtracts', () => {\n        expect(sub(3, 1)).toBe(2);\n      });",
        "  /*\n      it('subtracts', () => {\n        expect(sub(3, 1)).toBe(2);\n      });\n      */",
    )
    assert sev(modify("src/calc.test.js", JS_TWO, a), "test-commented-out") == ["high"]


def test_new_comment_that_looks_like_an_assert_is_not_flagged():
    b = "def test_v():\n    assert v() == 3\n"
    a = "def test_v():\n    # assert w() later, once w exists\n    assert v() == 3\n"
    assert sev(modify("tests/test_a.py", b, a), "test-commented-out") == []


def test_commented_code_in_non_test_file_is_not_flagged():
    b = "def f():\n    assert x\n"
    assert sev(modify("src/a.py", b, b.replace("    assert x", "    # assert x")), "test-commented-out") == []


# ------------------------------------------------------------------- general


def test_new_test_file_is_not_flagged():
    assert analyze_diff(add_file("tests/test_new.py", PY_TWO_TESTS)) == []


def test_new_tests_appended_are_not_flagged():
    assert analyze_diff(modify("tests/test_calc.py", PY_ONE_TEST, PY_TWO_TESTS)) == []


def test_it_changed_to_fit_or_xit_is_not_a_deletion():
    assert _js_deleted("fit") + _js_deleted("xit") + _js_deleted("xtest") == []


def _js_deleted(prefix):
    return sev(modify("src/parse.test.js", JS_BASE, JS_BASE.replace("it('reads", prefix + "('reads")), "test-deleted")


def test_encoding_or_standard_names_are_not_issue_keys():
    lines = ['@pytest.mark.skip(reason="UTF-8 decoding broken")', '@pytest.mark.skip(reason="SHA-256 differs")',
             '@pytest.mark.skip(reason="ISO-8601 parsing")']
    assert [sev(modify("tests/test_p.py", PY_BASE, _py_with(x)), "skip-added") for x in lines] == [["high"]] * 3


# ------------------------------------- test-commented-out: triple-quoted strings


DOC_BASE = "def test_a():\n    assert f() == 1\n\n\ndef test_b():\n    assert g() == 2\n"


def test_docstring_added_to_a_test_is_not_commented_out():
    after = DOC_BASE.replace("def test_a():\n", 'def test_a():\n    """Check f.\n\n    More detail.\n    """\n')
    assert analyze_diff(modify("tests/test_x.py", DOC_BASE, after)) == []


def test_one_line_docstring_added_is_not_commented_out():
    after = DOC_BASE.replace("def test_b():\n", 'def test_b():\n    """Check g."""\n')
    assert analyze_diff(modify("tests/test_x.py", DOC_BASE, after)) == []


def test_docstrings_added_to_two_tests_are_not_commented_out():
    after = DOC_BASE.replace("def test_a():\n", "def test_a():\n    '''A.\n    '''\n").replace(
        "def test_b():\n", "def test_b():\n    '''B.\n    '''\n")
    assert analyze_diff(modify("tests/test_x.py", DOC_BASE, after)) == []


def test_existing_asserts_wrapped_in_added_triple_quotes_are_flagged():
    b = "def test_v():\n    x = v()\n    assert x == 3\n    assert w()\n"
    a = 'def test_v():\n    x = v()\n    """\n    assert x == 3\n    assert w()\n    """\n'
    assert sev(modify("tests/test_a.py", b, a), "test-commented-out") == ["high"]


def test_removed_assert_re_added_inside_added_triple_quotes_is_flagged():
    b = "def test_v():\n    assert v() == 3\n"
    a = 'def test_v():\n    """\n    assert v() == 3\n    """\n    pass\n'
    assert sev(modify("tests/test_a.py", b, a), "test-commented-out") == ["high"]


# ------------------------------------------------ skip-added: what counts as a link


def _skip_reason(reason):
    return sev(modify("tests/test_p.py", PY_BASE, _py_with("@pytest.mark.skip(reason=%r)" % reason)), "skip-added")


def test_bare_one_digit_hash_is_not_an_issue_link():
    assert [_skip_reason(r) for r in ("flaky #1", "issue #5", "flaky #12")] == [["high"]] * 3


def test_hash_number_after_a_tracker_word_is_an_issue_link():
    reasons = ("see #12", "tracked in #345", "bug #77", "Fixes #1024", "ticket: #42", "blocked by #77")
    assert [_skip_reason(r) for r in reasons] == [["low"]] * len(reasons)


def test_gh_number_after_a_tracker_word_and_an_issue_url_are_issue_links():
    # Review 2: a bare gh-123 and any URL used to count; now the reference must name one issue.
    reasons = ("tracked in gh-123", "https://github.com/o/r/issues/9")
    assert [_skip_reason(r) for r in reasons] == [["low"]] * 2


def test_placeholder_keys_are_not_ticket_keys():
    reasons = ("TODO-1", "WIP-2 later", "FIXME-3", "C-3PO", "Python 3.12 bug", "PEP-8 style", "UTF-16 decode")
    assert [_skip_reason(r) for r in reasons] == [["high"]] * len(reasons)


def test_project_ticket_key_after_a_tracker_word_is_an_issue_link():
    assert [_skip_reason(r) for r in ("see PROJ-482", "blocked on CORE-17")] == [["low"]] * 2


def test_issue_link_on_the_comment_line_above_a_jest_skip_is_accepted():
    after = JS_BASE.replace("  it('reads", "  // Flaky on CI, tracked in https://github.com/o/r/issues/318\n      it.skip('reads")
    assert sev(modify("src/parse.test.js", JS_BASE, after), "skip-added") == ["low"]


def test_issue_link_on_the_comment_line_above_a_pytest_marker_is_accepted():
    line = "# see #4521\n    @pytest.mark.skip(reason='flaky')"
    assert sev(modify("tests/test_p.py", PY_BASE, _py_with(line)), "skip-added") == ["low"]


def test_issue_link_on_an_existing_comment_above_a_new_marker_is_not_accepted():
    # Review 3 (V2): the comment was already there, so its link does not vouch for the new skip.
    before = _py_with("# see #4521")
    after = before.replace("# see #4521\n", "# see #4521\n    @pytest.mark.skip(reason='flaky')\n")
    assert sev(modify("tests/test_p.py", before, after), "skip-added") == ["high"]


def test_issue_link_on_a_new_comment_above_a_new_marker_after_a_removed_line_is_accepted():
    before = _py_with("x = 1")
    after = before.replace("x = 1\n", "# see #4521\n    @pytest.mark.skip(reason='flaky')\n")
    assert sev(modify("tests/test_p.py", before, after), "skip-added") == ["low"]


def test_issue_link_two_lines_above_the_marker_is_not_accepted():
    line = "# see #4521\n    x = 1\n    @pytest.mark.skip(reason='flaky')"
    assert sev(modify("tests/test_p.py", PY_BASE, _py_with(line)), "skip-added") == ["high"]


# ------------------------------------------------- skip-added: environment gates


def _skipif(cond):
    return sev(modify("tests/test_p.py", PY_BASE, _py_with("@pytest.mark.skipif(%s, reason='env')" % cond)), "skip-added")


def test_skipif_on_python_version_or_platform_is_low():
    conds = ["sys.version_info < (3, 10)", "sys.version_info[:2] >= (3, 12)", 'sys.platform == "win32"',
             'sys.platform.startswith("linux")', 'platform.system() == "Windows"', 'os.name == "nt"',
             'importlib.util.find_spec("yaml") is None', 'shutil.which("git") is None',
             'sys.version_info < (3, 9) or sys.platform == "darwin"']
    assert [_skipif(c) for c in conds] == [["low"]] * len(conds)


def test_skipif_on_anything_else_stays_high():
    conds = ["True", "1", "compute() != 3", "sys.version_info < (3, 10) or BROKEN", "os.environ.get('CI')",
             "not HAS_FEATURE", "sys.modules['x'].broken"]
    assert [_skipif(c) for c in conds] == [["high"]] * len(conds)


def test_multiline_skipif_on_version_is_low():
    line = "@pytest.mark.skipif(\n        sys.version_info < (3, 10),\n        reason='needs match',\n    )"
    assert sev(modify("tests/test_p.py", PY_BASE, _py_with(line)), "skip-added") == ["low"]


def test_plain_skip_mentioning_a_version_is_high():
    assert _skip_reason("sys.version_info < (3, 10)") == ["high"]


# ------------------------------------- expected-changed: which source changes count


EXP_TEST = "import calc\n\n\ndef test_add():\n    assert calc.add(2, 2) == 4\n"
EXP_TEST_CHANGED = EXP_TEST.replace("== 4", "== 5")
CALC = "def add(a, b):\n    return a + b\n"


def test_real_edit_of_the_used_module_down_grades():
    diff = modify("tests/test_a.py", EXP_TEST, EXP_TEST_CHANGED) + modify(
        "calc.py", CALC, CALC.replace("a + b\n", "a + b + 1\n"))
    assert sev(diff, "expected-changed") == ["low"]


def test_string_edit_of_the_used_module_down_grades():
    src = "def add(a, b):\n    return f'{a}+{b}'  # x\n"
    diff = modify("tests/test_a.py", EXP_TEST, EXP_TEST_CHANGED) + modify("calc.py", src, src.replace("+{b}", "-{b}"))
    assert sev(diff, "expected-changed") == ["low"]


def test_comment_only_source_edit_does_not_down_grade():
    diff = modify("tests/test_a.py", EXP_TEST, EXP_TEST_CHANGED) + modify(
        "calc.py", CALC, CALC.replace("a + b\n", "a + b  # perf\n"))
    assert sev(diff, "expected-changed") == ["medium"]


def test_whitespace_only_source_edit_does_not_down_grade():
    diff = modify("tests/test_a.py", EXP_TEST, EXP_TEST_CHANGED) + modify(
        "calc.py", CALC, CALC.replace("a + b", "a  +  b") + "\n\n")
    assert sev(diff, "expected-changed") == ["medium"]


def test_source_edit_in_a_module_the_test_does_not_use_does_not_down_grade():
    diff = modify("tests/test_a.py", EXP_TEST, EXP_TEST_CHANGED) + modify(
        "src/report.py", "def r():\n    return 1\n", "def r():\n    return 2\n")
    assert sev(diff, "expected-changed") == ["medium"]


def test_source_edit_in_a_module_named_like_the_test_file_down_grades():
    b = "def test_add():\n    assert add(2, 2) == 4\n"
    diff = modify("tests/test_calc.py", b, b.replace("== 4", "== 5")) + modify(
        "src/calc.py", CALC, CALC.replace("a + b", "a + b + 1"))
    assert sev(diff, "expected-changed") == ["low"]


def test_source_edit_in_a_module_named_like_a_jest_test_file_down_grades():
    b = "it('adds', () => {\n  expect(add(2, 2)).toBe(4);\n});\n"
    diff = modify("test/calc.test.js", b, b.replace("toBe(4)", "toBe(5)")) + modify(
        "src/calc.js", "export const add = (a, b) => a + b;\n", "export const add = (a, b) => a + b + 1;\n")
    assert sev(diff, "expected-changed") == ["low"]


# ------------------------------------------- test-deleted: renamed and rewritten


JS_RENAME_BEFORE = """
    test('a custom fetch that resolves with a non-response throws', async () => {
      const server = await createHttpTestServer();
      server.get('/', (request, response) => { response.end('ok'); });
      await t.throwsAsync(ky(server.url, { fetch: async () => 'nope' }), { instanceOf: TypeError });
    });

    test('other', () => {
      expect(b()).toBe(2);
    });
"""
JS_RENAME_AFTER = """
    test('a non-response from custom fetch is a TypeError', async () => {
      const error = await t.throwsAsync(ky('https://example.com', { fetch: async () => 42 }));
      t.true(error instanceof TypeError);
    });

    test('other', () => {
      expect(b()).toBe(2);
    });
"""


def test_jest_test_renamed_with_a_new_body_is_low():
    assert sev(modify("test/fetch.test.js", JS_RENAME_BEFORE, JS_RENAME_AFTER), "test-deleted") == ["low"]


def test_pytest_test_renamed_with_a_new_body_is_low():
    b = 'def test_old():\n    result = compute_all(items, mode="fast")\n    assert result.total == 10\n\n\ndef test_other():\n    assert b() == 2\n'
    a = b.replace('def test_old():\n    result = compute_all(items, mode="fast")\n    assert result.total == 10\n',
                  "def test_session_runs_to_ten():\n    with open_session() as s:\n        assert s.run() == 10\n")
    assert sev(modify("tests/test_a.py", b, a), "test-deleted") == ["low"]


def test_rename_with_a_dropped_assert_still_reports_assert_removed():
    b = "def test_old():\n    assert a() == 1\n    assert a(2) == 4\n\n\ndef test_other():\n    assert b() == 2\n"
    a = b.replace("def test_old():\n    assert a() == 1\n    assert a(2) == 4\n",
                  "def test_a_returns_one_for_default_input():\n    value = a(None)\n    assert value == 1\n")
    assert sev(modify("tests/test_a.py", b, a), "assert-removed") == ["medium"]


def test_two_tests_replaced_by_one_stay_high():
    b = "def test_one():\n    assert a(1) == 1\n\n\ndef test_two():\n    assert a(2) == 2\n\n\ndef test_other():\n    assert b() == 2\n"
    a = b.replace("def test_one():\n    assert a(1) == 1\n\n\ndef test_two():\n    assert a(2) == 2\n",
                  "def test_all_values_round_trip_through_a():\n    for v in (1, 2):\n        assert a(v) == v\n")
    assert set(sev(modify("tests/test_a.py", b, a), "test-deleted")) == {"high"}


def test_test_removed_and_unrelated_test_added_elsewhere_stays_high():
    b = "def test_old():\n    assert a() == 1\n"
    filler = "".join("\n\ndef test_keep%d():\n    assert k(%d) == %d\n" % (i, i, i) for i in range(4))
    before = b + filler
    after = filler.lstrip("\n") + "\n\ndef test_brand_new_behaviour():\n    value = n()\n    assert value == 3\n"
    assert sev(modify("tests/test_a.py", before, after), "test-deleted") == ["high"]


# ------------------------------------------- test-deleted: parametrized case removed

PARAM = """
    import pytest


    @pytest.mark.parametrize("a,b", [
        (1, 2),
        (2, 4),
        (3, 7),
    ])
    def test_d(a, b):
        assert d(a) == b
"""


def test_parametrize_case_removed_is_medium():
    after = PARAM.replace("        (3, 7),\n", "")
    fs = only(modify("tests/test_d.py", PARAM, after), "test-deleted")
    assert [(f.severity, "parametrized case removed" in f.message) for f in fs] == [("medium", True)]


def test_parametrize_case_removed_when_the_decorator_is_outside_the_hunk_is_medium():
    before = PARAM.replace('        (1, 2),\n', "".join("        (%d, %d),\n" % (i, 2 * i) for i in range(10, 20)))
    after = before.replace("        (3, 7),\n", "")
    diff = modify("tests/test_d.py", before, after)
    assert "parametrize" not in diff.split("@@", 2)[2]  # the opener is not in the hunk
    assert sev(diff, "test-deleted") == ["medium"]


def test_jest_each_table_row_removed_is_medium():
    b = "describe('fee', () => {\n  it.each([\n    [0, 10],\n    [1, 8],\n    [2, 6],\n  ])('tier %i', (t, e) => {\n    expect(fee(t)).toBe(e);\n  });\n});\n"
    assert sev(modify("src/fee.test.js", b, b.replace("    [1, 8],\n", "")), "test-deleted") == ["medium"]


def test_parametrize_case_edited_is_not_a_removal():
    after = PARAM.replace("(3, 7)", "(3, 6)")
    assert sev(modify("tests/test_d.py", PARAM, after), "test-deleted") == []


def test_parametrize_case_added_is_not_flagged():
    after = PARAM.replace("        (3, 7),\n", "        (3, 7),\n        (4, 8),\n")
    assert analyze_diff(modify("tests/test_d.py", PARAM, after)) == []


def test_whole_parametrized_test_removed_reports_only_the_test():
    before = PARAM + "\n\n    def test_keep():\n        assert k() == 1\n"
    after = "\n    import pytest\n\n\n    def test_keep():\n        assert k() == 1\n"
    assert sev(modify("tests/test_d.py", before, after), "test-deleted") == ["high"]


def test_row_removed_from_a_plain_list_in_a_test_body_is_not_flagged():
    b = "def test_sum():\n    rows = [\n        (1, 2),\n        (3, 4),\n    ]\n    assert total(rows) == 10\n"
    assert sev(modify("tests/test_s.py", b, b.replace("        (3, 4),\n", "")), "test-deleted") == []


# ------------------------------------------------ skip-added: jest compound markers


@pytest.mark.parametrize("new", [
    "xit.each([[1]])('reads", "xtest.each([[1]])('reads", "fit.each([[1]])('reads", "it.failing('reads",
    "test.failing('reads", "xit.failing('reads", "xtest.failing('reads", "fit.failing('reads",
])
def test_jest_compound_it_markers_are_flagged_high(new):
    assert _js_skip("it('reads", new) == ["high"]


@pytest.mark.parametrize("new", ["xdescribe.each([[1]])('parse'", "fdescribe.each([[1]])('parse'"])
def test_jest_compound_describe_markers_are_flagged_high(new):
    assert _js_skip("describe('parse'", new) == ["high"]


def test_one_line_tagged_template_each_with_skip_is_flagged():
    assert _js_skip("it('reads", "it.skip.each`a | b`('reads") == ["high"]


def test_multi_line_tagged_template_each_with_only_is_flagged():
    assert _js_skip("it('reads", "it.only.each`\n    a    | b\n    ${1} | ${2}\n  `('reads") == ["high"]


# ---------------------------------------------------- skip-added: counted per file


def test_skip_removed_in_one_file_does_not_cancel_a_skip_added_in_another():
    a_before = "it('x', () => {\n  expect(1).toBe(1);\n});\n"
    diff = modify("test/a.test.js", a_before.replace("it('x'", "it.skip('x'"), a_before) + modify(
        "test/b.test.js", "it('y', () => {\n  expect(2).toBe(2);\n});\n", "it.skip('y', () => {\n  expect(2).toBe(2);\n});\n")
    assert [(f.path, f.severity) for f in only(diff, "skip-added")] == [("test/b.test.js", "high")]


def test_skipped_test_moved_to_another_file_keeps_its_skip_unflagged():
    body = "it.skip('x', () => {\n  expect(1).toBe(1);\n});\n"
    keep = "it('k', () => {\n  expect(0).toBe(0);\n});\n"
    diff = modify("test/a.test.js", keep + "\n" + body, keep) + modify("test/b.test.js", keep, keep + "\n" + body)
    assert sev(diff, "skip-added") == []


# ------------------------------------------ mutation-killing cases (validation round)


def test_changed_value_in_a_chained_multiline_expect_is_flagged():
    b = "it('total', () => {\n  expect(total(cart))\n    .toBe(150);\n});\n"
    assert _exp("src/t.test.js", b, b.replace("toBe(150)", "toBe(160)")) == ["medium"]


def test_bare_approx_given_a_looser_rel_is_flagged():
    b = "def test_v():\n    assert v() == pytest.approx(1.5)\n"
    assert _tol("tests/test_calc.py", b, b.replace("approx(1.5)", "approx(1.5, rel=1e-3)")) == ["high"]


def test_docstring_first_line_edited_far_above_other_hunks_is_not_commented_out():
    # Hunk 1 edits the opening line of a long docstring whose closing quotes are in the unchanged
    # gap; hunk 2 has existing asserts and a new docstring. The pairing must not carry over the gap.
    doc = "".join("    line %d of the docstring\n" % i for i in range(20))
    before = 'def test_a():\n    """Old summary.\n' + doc + '    """\n    assert a() == 1\n' + "".join(
        "\n\ndef test_k%d():\n    assert k(%d) == %d\n" % (i, i, i) for i in range(3))
    after = before.replace('"""Old summary.', '"""New summary.').replace(
        "def test_k2():\n", 'def test_k2():\n    """K2."""\n').replace(
        "def test_k1():\n", 'def test_k1():\n    """K1.\n\n    More.\n    """\n')
    diff = modify("tests/test_a.py", before, after)
    assert diff.count("\n@@ ") == 2  # two hunks
    assert sev(diff, "test-commented-out") == []


def test_parametrize_case_replaced_by_other_new_cases_is_not_a_removal():
    # The removed row is too unlike the new ones to pair, as in pydantic-settings e9588aef.
    after = PARAM.replace("        (3, 7),\n", "        (Json[list[int] | str], '[\"q\"]', ['q']),\n"
                                             "        (typing.Optional[list[int]], 'null', None),\n")
    assert sev(modify("tests/test_d.py", PARAM, after), "test-deleted") == []
