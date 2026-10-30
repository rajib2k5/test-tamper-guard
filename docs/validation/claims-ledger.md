# Claims ledger (pre-registered 2026-10-29, before either channel ran)

Mode 1: two independent subagents. Channel A reads documentation only. Channel B runs probes only.
Every material claim starts REJECTED. The code under validation is `src/`, `hooks/`, `action.yml`,
`.claude-plugin/`, `.github/workflows/`.

| ID | Cat. | Claim | Material |
|---|---|---|---|
| C1 | Semantic | `pytest.approx(expected, rel=..., abs=...)` accepts `rel` and `abs`, and a larger `rel` or `abs` accepts more values (looser). | yes |
| C2 | Semantic | `@pytest.mark.skip`, `@pytest.mark.skipif(cond, reason=...)`, `@pytest.mark.xfail`, `pytest.skip()` and `pytest.xfail()` each stop a failing test from failing the run. | yes |
| C3 | API/Semantic | `unittest.TestCase.assertAlmostEqual(first, second, places=None, msg=None, delta=None)`: fewer `places` or a larger `delta` is looser. `unittest.skip`, `skipIf`, `skipUnless`, `expectedFailure` stop a failing test from failing the run. | yes |
| C4 | API/Semantic | `numpy.testing.assert_allclose(actual, desired, rtol=1e-07, atol=0)` and `torch.testing.assert_close(actual, expected, rtol=, atol=)`: larger `rtol`/`atol` is looser. | yes |
| C5 | Semantic | jest `expect(x).toBeCloseTo(y, numDigits)` (default 2): a smaller `numDigits` is looser. | yes |
| C6 | API/Semantic | jest `it.skip`, `test.skip`, `describe.skip`, `xit`, `xtest`, `xdescribe`, `test.todo`, `test.failing` stop a test from failing the run; `it.only`, `test.only`, `fit`, `fdescribe`, `describe.only` stop the other tests in the file from running. The engine flags every one of these when added. | yes |
| C7 | API | Claude Code PreToolUse hook input on stdin has `tool_name`, `tool_input`, `cwd`; `Write` input has `file_path`, `content`; `Edit` has `file_path`, `old_string`, `new_string`, `replace_all`; `MultiEdit` (if it still exists) has `file_path`, `edits[]`. Output `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask"|"deny", "permissionDecisionReason": str}}` on stdout with exit 0 makes Claude Code ask / deny. | yes |
| C8 | Environmental | A plugin with `.claude-plugin/plugin.json` and `hooks/hooks.json` registers its hooks only when the plugin is installed and enabled; `${CLAUDE_PLUGIN_ROOT}` expands to the plugin directory in the hook command. | yes |
| C9 | API | GitHub workflow commands `::error file=F,line=L,title=T::MSG` and `::warning ...` create annotations. Message data escapes `%`→`%25`, `\r`→`%0D`, `\n`→`%0A`; property values also escape `:`→`%3A`, `,`→`%2C`. The CLI's `--format github` follows this. | yes |
| C10 | Environmental | In a composite action, `$GITHUB_ACTION_PATH` is the action's directory; `github.event.pull_request.base.sha`/`head.sha` exist on `pull_request` events; the caller needs `actions/checkout` with `fetch-depth: 0` for `git diff base head` to work. | yes |
| C11 | API | `git diff -M` emits `rename from X` / `rename to Y`, `new file mode`, `deleted file mode`, `--- /dev/null`, `Binary files ... differ`, C-quoted paths (`"a/sp\303\251c.py"`) when `core.quotePath` is on, and `\ No newline at end of file`. The parser handles each. | yes |
| C12 | Environmental | `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` is tag v7.0.1 and `actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` is tag v7.1.0. | yes |
| C13 | Environmental | `src/` and `hooks/` run on Python 3.9 (no 3.10+ syntax or stdlib API). | yes |
