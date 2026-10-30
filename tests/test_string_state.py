"""Removed and context lines inside docstrings, block comments and multi-line template
literals are not code (second review, scratchpad review2/c2*.py)."""

from _diff import modify

from test_tamper_guard.engine import analyze_diff

P = "tests/test_x.py"
J = "test/x.test.js"
PAD = "\n".join("    line %d" % i for i in range(10))


def rules(diff):
    return sorted("%s:%s" % (f.rule, f.severity) for f in analyze_diff(diff))


# ------------------------------------------------------------------- Python


def test_example_assert_removed_from_a_small_docstring_is_not_assert_removed():
    d = 'def test_a():\n    """Doc.\n\n    Example::\n\n        assert parse("1") == 1\n    """\n    assert f() == 1\n'
    assert rules(modify(P, d, d.replace('    Example::\n\n        assert parse("1") == 1\n', ""))) == []


def test_whole_docstring_with_an_example_assert_removed_is_not_assert_removed():
    d = 'def test_a():\n    """Doc.\n\n    Example::\n\n        assert parse("1") == 1\n    """\n    assert f() == 1\n'
    assert rules(modify(P, d, "def test_a():\n    assert f() == 1\n")) == []


def test_example_test_removed_inside_a_docstring_whose_opener_is_outside_the_hunk():
    d = 'def test_a():\n    """Doc.\n%s\n    def test_example():\n        assert x == 1\n    """\n    assert f() == 1\n' % PAD
    diff = modify(P, d, d.replace("    def test_example():\n        assert x == 1\n", ""))
    assert '"""Doc.' not in diff  # the opener is not in the hunk
    assert rules(diff) == []


def test_example_test_removed_right_after_a_docstring_opener_in_the_hunk():
    d = 'def test_a():\n    """Doc.\n    def test_example():\n        assert x == 1\n%s\n    """\n    assert f() == 1\n' % PAD
    assert rules(modify(P, d, d.replace("    def test_example():\n        assert x == 1\n", ""))) == []


def test_skip_text_added_inside_a_docstring_whose_opener_is_outside_the_hunk():
    d = 'def test_a():\n    """Doc.\n%s\n    def test_example():\n        assert x == 1\n    """\n    assert f() == 1\n' % PAD
    diff = modify(P, d, d.replace("    def test_example():\n", "    @pytest.mark.skip\n    def test_example():\n"))
    assert rules(diff) == []


def test_def_test_added_inside_a_docstring_does_not_cancel_a_real_deletion():
    d = "def test_keep():\n    assert k() == 1\n\n\ndef test_gone():\n    assert g() == 2\n"
    a = 'def test_keep():\n    """Was:\n\n    def test_gone():\n    """\n    assert k() == 1\n'
    assert "test-deleted:high" in rules(modify(P, d, a))


def test_real_assert_removed_after_a_docstring_is_still_reported():
    d = 'def test_a():\n    """Doc.\n\n    More.\n    """\n    assert f() == 1\n    assert f(2) == 2\n'
    assert rules(modify(P, d, d.replace("    assert f(2) == 2\n", ""))) == ["assert-removed:medium"]


def test_real_test_removed_below_a_closed_docstring_is_still_reported():
    d = 'def test_a():\n    """Doc."""\n    assert f() == 1\n\n\ndef test_b():\n    """B.\n\n    More.\n    """\n    assert g() == 2\n'
    a = 'def test_a():\n    """Doc."""\n    assert f() == 1\n'
    assert rules(modify(P, d, a)) == ["test-deleted:high"]


def test_existing_asserts_wrapped_in_added_triple_quotes_are_still_commented_out():
    b = "def test_v():\n    x = v()\n    assert x == 3\n    assert w()\n"
    a = 'def test_v():\n    x = v()\n    """\n    assert x == 3\n    assert w()\n    """\n'
    assert "test-commented-out:high" in rules(modify(P, b, a))


# ----------------------------------------------------------------------- JS


def test_example_test_removed_inside_a_block_comment_whose_opener_is_outside_the_hunk():
    bc = "/*\n%s\n test('example', () => {\n   expect(1).toBe(1);\n });\n*/\ntest('a', () => {\n  expect(f()).toBe(1);\n});\n" % (
        "\n".join(" * c%d" % i for i in range(10)))
    diff = modify(J, bc, bc.replace(" test('example', () => {\n   expect(1).toBe(1);\n });\n", ""))
    assert "/*" not in diff
    assert rules(diff) == []


def test_expect_removed_from_a_multi_line_template_literal_is_not_assert_removed():
    jt = "test('a', () => {\n  const u = `line1\n// it.skip('x')\nexpect(1).toBe(1)\nline4`;\n  expect(f()).toBe(1);\n});\n"
    assert rules(modify(J, jt, jt.replace("expect(1).toBe(1)\n", ""))) == []


def test_one_line_block_comment_with_an_expect_removed_is_not_assert_removed():
    b = "test('a', () => {\n  /* expect(g()).toBe(2); */\n  expect(f()).toBe(1);\n});\n"
    assert rules(modify(J, b, b.replace("  /* expect(g()).toBe(2); */\n", ""))) == []


def test_real_expect_removed_after_a_regex_with_slash_star_is_still_reported():
    b = "test('a', () => {\n  const r = /\\/*/;\n  expect(f()).toBe(1);\n  expect(f(2)).toBe(2);\n});\n"
    assert rules(modify(J, b, b.replace("  expect(f(2)).toBe(2);\n", ""))) == ["assert-removed:medium"]


def test_real_expect_removed_after_a_slash_star_string_is_still_reported():
    b = "test('a', () => {\n  const s = '/*';\n  expect(f()).toBe(1);\n  expect(f(2)).toBe(2);\n});\n"
    assert rules(modify(J, b, b.replace("  expect(f(2)).toBe(2);\n", ""))) == ["assert-removed:medium"]


def test_real_expect_removed_after_a_closed_block_comment_is_still_reported():
    b = "test('a', () => {\n  /* start\n%s\n  */\n  expect(f()).toBe(1);\n  expect(f(2)).toBe(2);\n});\n" % (
        "\n".join("  c%d" % i for i in range(10)))
    assert rules(modify(J, b, b.replace("  expect(f(2)).toBe(2);\n", ""))) == ["assert-removed:medium"]


def test_expected_value_in_a_one_line_template_literal_is_still_compared():
    b = "it('greets', () => {\n  expect(greet('a')).toBe(`hi a`);\n});\n"
    assert rules(modify(J, b, b.replace("`hi a`", "`hello a`"))) == ["expected-changed:medium"]


def test_tagged_template_each_with_only_is_still_a_skip_marker():
    b = "it('reads', () => {\n  expect(r()).toBe(1);\n});\n"
    a = "it.only.each`\n    a    | b\n    ${1} | ${2}\n  `('reads', () => {\n  expect(r()).toBe(1);\n});\n"
    assert "skip-added:high" in rules(modify(J, b, a))


def test_value_changed_inside_an_inline_snapshot_is_reported_with_the_real_text():
    b = "test('a', () => {\n  expect(f()).toMatchInlineSnapshot(`\n    \"old value\"\n  `)\n});\n"
    fs = [x for x in analyze_diff(modify(J, b, b.replace("old value", "new value"))) if x.rule == "expected-changed"]
    assert [("old value" in x.message, "new value" in x.message) for x in fs] == [(True, True)]


def test_skip_added_inside_a_template_fixture_whose_opener_is_above_the_hunk():
    # vitest 21be412e: a hunk that starts inside one runInlineTests fixture template and adds
    # a second one whose source holds it.skip(...).
    inner = "\n".join("      line%d()" % i for i in range(10))
    b = "test('a', async () => {\n  await run({\n    'a.test.js': `\n%s\n    `,\n  })\n})\n" % inner
    a = b + "\ntest('b', async () => {\n  await run({\n    'b.test.js': `\n      it.skip('static', () => {})\n    `,\n  })\n})\n"
    diff = modify(J, b, a)
    assert "'a.test.js'" not in diff  # the first template's opener is not in the hunk
    assert rules(diff) == []
