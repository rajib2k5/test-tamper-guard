# Channel A — documentation audit

Auditor: Channel A (docs and library source only). Retrieved 2026-10-29.
Rules followed: no execution of the project's code and no probes of it. I read the project
source only to see which symbols and patterns it uses, and for C6(b), C9(b), C11(b) and C13 I
judged by reading the source against the docs. I did not read `channel-b.md`.
Copies of the docs I retrieved are in
`/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/docs/`.

## Version pin (checked 2026-10-29)

| Thing | Current (registry) | Pinned in project | Docs used |
|---|---|---|---|
| pytest | 9.2.0 (PyPI) | 8.4.2 (`uv.lock`, dev only) | source at tags 9.2.0 and 8.4.2 |
| numpy | 2.5.4 (PyPI) | not a dependency | source at tag v2.5.4 |
| torch | 2.15.0 (PyPI) | not a dependency | source at tag v2.15.0 |
| jest | 30.5.2 (npm) | not a dependency | `website/versioned_docs/version-30.5` at tag v30.5.2 |
| Python | — | `requires-python >=3.9`; CI matrix 3.9, 3.12 | docs.python.org/3.9 and /3.14 |
| Claude Code | 2.1.314 (top of CHANGELOG.md) | — | code.claude.com/docs (last-modified 2026-10-30 01:21 GMT) |
| git | 2.56.0 (latest tag); local 2.43.0 | — | git/git master `Documentation/`, `diff.c` |
| actions/toolkit | `packages/core/src/command.ts` last changed 2026-01-29 | — | main branch |

---

## C1 — pytest.approx rel/abs

```
claim_id:    C1
verdict:     CONFIRMED
source:      https://github.com/pytest-dev/pytest/blob/9.2.0/src/_pytest/approx.py (L607-652, L774-779)
             https://github.com/pytest-dev/pytest/blob/8.4.2/src/_pytest/python_api.py (L522, L551)
source_tier: 2 (library source, which holds the reference docstring)
version:     pytest 9.2.0 and 8.4.2
quote:       "# Return the larger of the relative and absolute tolerances."
retrieved:   2026-10-29
note:        Signature: approx(expected, rel=None, abs=None, nan_ok=False). The check is
             abs(expected - actual) <= max(rel*|expected|, abs), so it is monotone in rel and in abs.
```
Caveat the engine has to respect: the comparison is monotone only while the *set* of given
parameters stays the same. Docstring: "If you specify ``abs`` but not ``rel``, the comparison will
not consider the relative tolerance at all". So `approx(x)` → `approx(x, abs=1e-12)` is a
*tightening* (the default rel=1e-6 is dropped), even though a parameter was "added". In 9.2 the code moved
from `python_api.py` to `approx.py`, and `rel`/`abs` also accept `timedelta`.

## C2 — pytest skip / skipif / xfail / pytest.skip() / pytest.xfail()

```
claim_id:    C2
verdict:     CONFIRMED (with documented exceptions, see note)
source:      https://github.com/pytest-dev/pytest/blob/9.2.0/doc/en/how-to/skipping.rst (L8-20, L53-60, L85, L228-244, L289-301, L319-348)
source_tier: 1
version:     pytest 9.2.0
quote:       "present a summary of the test session, while keeping the test suite *green*."
retrieved:   2026-10-29
note:        skip: test is not run. skipif: skips only when the condition is true. xfail:
             "no traceback will be reported when it fails" (listed as XFAIL). pytest.skip()
             and pytest.xfail() are the imperative forms.
```
Documented exceptions, where the marker does *not* stop the failure:
`@pytest.mark.xfail(raises=E)` — "reported as a regular failure if it fails with an exception not
mentioned in ``raises``"; `skipif(False, ...)` does nothing; the `--runxfail` option disables xfail.
`strict=True` affects only XPASS (a passing test), not a failing one.

## C3 — unittest assertAlmostEqual and skip decorators

```
claim_id:    C3
verdict:     CONFIRMED
source:      https://docs.python.org/3.9/library/unittest.html#unittest.TestCase.assertAlmostEqual
             https://docs.python.org/3.14/library/unittest.html (same text)
             https://github.com/python/cpython/blob/3.9/Lib/unittest/case.py (L848, L880-882)
source_tier: 1 (docs), 2 (source)
version:     Python 3.9 and 3.14
quote:       "rounding to the given number of decimal places (default 7), and comparing to zero."
retrieved:   2026-10-29
note:        Docs show places=7. The source signature is places=None, which is set to 7 when
             delta is None, so the claim's "places=None" matches the source. Fewer places means
             coarser rounding, so more values pass. With delta: "must be less or equal to ... delta".
             "Supplying both delta and places raises a TypeError."
```
Skips: "@unittest.skip(reason) Unconditionally skip the decorated test"; skipIf "if condition is
true"; skipUnless "unless condition is true"; expectedFailure: "If the test fails or errors in the
test function itself ... it will be considered a success." Docs exception: a failure *in a fixture
method* (setUp) is not covered by expectedFailure.

## C4 — numpy.testing.assert_allclose and torch.testing.assert_close

```
claim_id:    C4
verdict:     CONFIRMED
source:      https://github.com/numpy/numpy/blob/v2.5.4/numpy/testing/_private/utils.py (L1671, L1683-1686)
             https://github.com/pytorch/pytorch/blob/v2.15.0/torch/testing/_comparison.py (L160-165, L1415-1435)
source_tier: 2 (source, which holds the published docstrings)
version:     numpy 2.5.4; torch 2.15.0
quote:       numpy: "compares the difference between `actual` and `desired` to ``atol + rtol * abs(desired)``."
retrieved:   2026-10-29
note:        numpy signature assert_allclose(actual, desired, rtol=1e-7, atol=0, equal_nan=True, ...).
             torch: |actual - expected| <= atol + rtol * |expected|. Both are monotone in rtol and atol.
```
torch details the claim omits: `rtol` and `atol` are **keyword-only** (`*,` before them) and default
to `None`, which means dtype-based defaults. "Both 'rtol' and 'atol' must be either specified or omitted"
(passing only one is a ValueError). In numpy, `rtol` and `atol` may be passed positionally.

## C5 — jest toBeCloseTo numDigits

```
claim_id:    C5
verdict:     CONFIRMED
source:      https://github.com/jestjs/jest/blob/v30.5.2/website/versioned_docs/version-30.5/ExpectAPI.md (`.toBeCloseTo(number, numDigits?)`)
source_tier: 1
version:     jest 30.5
quote:       "the test criterion is `Math.abs(expected - received) < 0.005` (that is, `10 ** -2 / 2`)"
retrieved:   2026-10-29
note:        Default numDigits is 2. The threshold is 10**-numDigits / 2, so a smaller numDigits gives a
             larger threshold, which is looser.
```

## C6 — jest skip / focus modifiers; engine flags each

Split into C6(a) jest semantics (docs) and C6(b) engine coverage (source read against docs).

```
claim_id:    C6(a)
verdict:     CONFIRMED
source:      https://github.com/jestjs/jest/blob/v30.5.2/website/versioned_docs/version-30.5/GlobalAPI.md
             (sections describe.only L335, describe.skip L402, test.failing L751, test.only L831, test.skip L896, test.todo L959)
source_tier: 1
version:     jest 30.5
quote:       test.only: "the only ones you want to run in that test file."
retrieved:   2026-10-29
note:        Aliases as documented: test.skip = it.skip, xit, xtest; describe.skip = xdescribe;
             test.only = it.only, fit; describe.only = fdescribe. test.failing: "If `failing` test will throw any
             errors then it will pass." test.failing is "only available with the default jest-circus runner".
             test.todo takes no body, so the test does not run. The docs say only that it is "highlighted in
             the summary". They do not state "does not fail the run" in those words.
```

```
claim_id:    C6(b)
verdict:     CONFIRMED for the 13 call forms listed in the claim; GAPS for other documented alias forms
source:      src/test_tamper_guard/rules.py L275-279 (JS_SKIP_RE, JS_MARKERS), L286-318 (skip_markers, is_focus);
             engine.py L204-222 (skip-added), L85-99 (removed_markers)
source_tier: project source read against GlobalAPI.md v30.5
version:     jest 30.5 docs
quote:       GlobalAPI.md L920: "Also under the aliases: `it.skip.each(table)(name, fn)`, `xit.each(table)(name, fn)`, ..."
retrieved:   2026-10-29
```
By reading: alternative 1 of `JS_SKIP_RE`, `(it|test|describe|suite|context)((?:\.\w+)+)\s*[(\`]`
with `JS_MARKERS = skip, only, todo, failing, skipIf`, catches it.skip, test.skip, describe.skip,
test.todo, test.failing, it.only, test.only, describe.only, and also chains like `test.skip.each(`.
Alternative 2, `(xit|xtest|xdescribe|xcontext|fit|fdescribe|ftest)\s*\(`, catches the bare xit, xtest,
xdescribe, fit, fdescribe. So each form *as written in the claim* is matched when it is added to a test file.

Gaps found by reading. They are outside the claim's literal list, but they are documented aliases of
the same modifiers. Channel B should confirm or refute them:
1. **Documented compound aliases are not matched**: `xit.each(...)`, `xtest.each(...)`,
   `xdescribe.each(...)`, `fit.each(...)`, `fdescribe.each(...)`, `xit.failing(...)`, `xtest.failing(...)`,
   `fit.failing(...)` (GlobalAPI L359, L428, L809, L821, L857, L920). Alternative 2 needs `(` directly
   after the bare name. Alternative 1's lookbehind `(?<![\w$.])` blocks the match on `it` inside `xit`.
2. **Single-line tagged-template form**: `code_part` runs `strip_strings` first, which turns
   `` test.skip.each`a | b` `` into `test.skip.each""`. The regex needs `(` or a backtick after the chain,
   so the one-line template form looks unmatched. The multi-line form still matches: its opening
   backtick has no closing one on that line, so it is not stripped.
3. **"Every one when added" is not unconditional**: `facts.removed_markers` is a single `Counter`
   collected over **every file in the diff** (engine.py L85-99). An added marker is skipped when a
   removed marker of the same kind exists anywhere in the diff (L208-211). So un-skipping test A and
   skipping test B (even in another file) gives no finding for B.
4. Only files that pass `is_test_file` are checked (a test-name pattern or a test directory). A `.only`
   in a JS file outside those paths is not flagged. This looks deliberate.

## C7 — Claude Code PreToolUse hook contract

```
claim_id:    C7
verdict:     CONFIRMED for every non-MultiEdit part; MultiEdit part UNVERIFIABLE (not a documented tool)
source:      https://code.claude.com/docs/en/hooks (raw: /docs/en/hooks.md) L19, L735, L1161, L1765-1773, L1831-1849, L1957-1970, L944
             https://code.claude.com/docs/en/tools-reference (raw .md) L21-66 tool table
             https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md
source_tier: 1
version:     Claude Code docs as of 2026-10-30 01:21 GMT; CHANGELOG top = 2.1.314
quote:       "`[plugin:<name>]` for a plugin's hook"  (label shown when a hook returns "ask")
retrieved:   2026-10-29
```
Point by point:
- stdin: "For command hooks, input arrives on stdin." (L19). The common fields include `cwd`, "Current
  working directory when the hook is invoked" (L735). The PreToolUse example has `tool_name` and `tool_input`.
- Write: `file_path`, `content` (L1831-1837). Edit: `file_path`, `old_string`, `new_string`,
  `replace_all` (L1841-1848). Docs: "For the file tools `Write`, `Edit`, and `Read`, `tool_input.file_path`
  is always absolute" (L1758).
- **MultiEdit**: it does not appear in the hooks reference, in the tools-reference table (L21-66, which
  lists every built-in tool, Edit and Write included), or in CHANGELOG.md (0 matches for `multi.?edit`). I can find no current
  doc for `edits[]`, so the field claim is UNVERIFIABLE. The docs suggest MultiEdit is not a current
  tool. Matching `Write|Edit|MultiEdit` in `hooks/hooks.json` is harmless, but the MultiEdit branch in
  `hooks/pretooluse.py` is untested against any documented contract.
- Output: decision table "PreToolUse | `hookSpecificOutput` | `permissionDecision` (allow/deny/ask/defer),
  `permissionDecisionReason`" (L1161). The deny example includes `"hookEventName": "PreToolUse"`.
  "Exit 0 means success, and is the intended exit code when you print JSON". "`"ask"` prompts the user to
  confirm" (L1961). "`"deny"` prevents the tool call."
- **ask from a plugin hook is honoured**: L1970 says the "ask" prompt carries a source label, with
  `[plugin:<name>]` for a plugin's hook. Nothing in the docs says plugin hooks are limited to fewer decisions.
- Documented limits: "Deny and ask rules are still evaluated regardless of what the hook returns" (L1961).
  In a `-p` (non-interactive) run where nobody can answer, Claude Code denies the call and Claude sees the
  reason (L1962). Auto mode has its own section (L1990-1994). Precedence across hooks:
  `deny` > `defer` > `ask` > `allow` (L1966). Exit codes other than 0 and 2 count as failure even when JSON
  was printed (L944). The hook ends with `sys.exit(0)`, which is consistent with this.

## C8 — plugin hooks registration and ${CLAUDE_PLUGIN_ROOT}

```
claim_id:    C8
verdict:     CONFIRMED
source:      https://code.claude.com/docs/en/hooks (hook-location table; "When a plugin is enabled, its hooks merge ...")
             https://code.claude.com/docs/en/plugins-reference (Manifest file; Standard layout; Environment variables)
source_tier: 1
version:     Claude Code docs as of 2026-10-30 GMT
quote:       "Plugin `hooks/hooks.json` | When plugin is enabled | Yes, bundled with the plugin"
retrieved:   2026-10-29
note:        plugins-reference: hook commands resolve ${...} "Anywhere in `command` and `args`".
             ${CLAUDE_PLUGIN_ROOT} = "Absolute path of the plugin's installed version". It is also exported as an env var.
```
Details: `plugin.json` is **optional** ("The manifest is optional"), so `hooks/hooks.json` loads
without it. `hooks/hooks.json` must wrap the event map in a top-level `"hooks"` key, and the project's
file does. The project quotes the variable (`"${CLAUDE_PLUGIN_ROOT}/..."`), which matches the shell-form
quoting advice. Exceptions: `allowManagedHooksOnly` blocks plugin hooks unless the plugin is force-enabled
in managed `enabledPlugins`. `${CLAUDE_PLUGIN_ROOT}` changes when the plugin updates.

## C9 — GitHub workflow-command annotations and escaping; CLI follows

```
claim_id:    C9(a)
verdict:     CONFIRMED
source:      https://github.com/github/docs/blob/main/content/actions/reference/workflows-and-actions/workflow-commands.md (L167-216)
             https://github.com/actions/toolkit/blob/main/packages/core/src/command.ts (escapeData, escapeProperty; last commit 2026-01-29)
source_tier: 1 (syntax), 2 (escaping; the docs page itself does not spell out the escaping, 0 matches for %25)
version:     docs main; toolkit main @ ed3ea3b
quote:       "::error file={name},line={line},endLine={endLine},title={title}::{message}"
retrieved:   2026-10-29
note:        escapeData: % -> %25, \r -> %0D, \n -> %0A. escapeProperty: the same, then : -> %3A, , -> %2C.
```
```
claim_id:    C9(b)
verdict:     CONFIRMED (by reading)
source:      src/test_tamper_guard/cli.py L23-30 (escape_data, escape_property), L85-93 (format_github)
note:        Same replacements in the same order as the toolkit (% first). `file` and `title` go through
             escape_property, the message through escape_data. `line` is an integer (%d). high -> ::error, others -> ::warning.
```

## C10 — composite action path, PR SHAs, checkout depth

```
claim_id:    C10
verdict:     CONFIRMED
source:      https://github.com/github/docs/blob/main/content/actions/reference/workflows-and-actions/variables.md (L34)
             .../events-that-trigger-workflows.md (L462-482); .../contexts.md (L190)
             https://github.com/octokit/webhooks/blob/main/payload-schemas/api.github.com/common/pull-request.schema.json (base/head required, each requires sha)
             https://github.com/actions/checkout/blob/3d3c42e5aac5ba805825da76410c181273ba90b1/action.yml (fetch-depth default 1) and README L31
source_tier: 1 (GitHub docs, checkout at the pinned SHA); 2 (octokit payload schema)
version:     docs main; checkout v7.0.1
quote:       GITHUB_ACTION_PATH: "This property is only supported in composite actions."
retrieved:   2026-10-29
note:        checkout README: "Only a single commit is fetched by default". "Set `fetch-depth: 0` to fetch all history".
             events doc names `github.event.pull_request.head.sha`. The PR schema requires base.sha and head.sha.
```
Note: `fetch-depth: 0` is enough but not the only way (fetching the two SHAs would also work). Docs
say the default is depth 1, so the base commit is missing without some extra fetch. On `pull_request`,
checkout checks out the merge commit by default, which does not stop `git diff base head`.

## C11 — git diff -M output forms; parser handles each

```
claim_id:    C11(a)
verdict:     CONFIRMED
source:      https://github.com/git/git/blob/master/Documentation/diff-generate-patch.adoc (L20-42, L63-64, L152-158)
             https://github.com/git/git/blob/master/Documentation/config/core.adoc (core.quotePath, L159-172)
             https://github.com/git/git/blob/master/diff.c (L1868 nneof; L3959, L3983 "Binary files %s and %s differ")
             https://github.com/git/git/blob/master/Documentation/diff-options.adoc (L571 `-M[<n>]` "Detect renames.")
source_tier: 1 (docs), 2 (diff.c for two strings the docs do not spell out)
version:     git master @ b9e5cff (2026-10-29), latest tag v2.56.0
quote:       core.quotePath: "bytes with values larger than 0x80 (e.g. octal `\302\265` ...)"
retrieved:   2026-10-29
note:        Extended headers include "deleted file mode <mode>", "new file mode <mode>", "rename from <path>",
             "rename to <path>". "`/dev/null` is used to signal created or deleted files". core.quotePath "default value is true".
             "\ No newline at end of file" and "Binary files ... differ" are confirmed from diff.c source only; the patch-format doc does not list them.
```
```
claim_id:    C11(b)
verdict:     CONFIRMED (by reading; not executed)
source:      src/test_tamper_guard/diffparse.py L53-76 (_unquote), L83-91, L94-118, L136-165, L175-189, L210-223
note:        rename from/to: set is_rename and paths, and quoted names are unquoted. new/deleted file mode: set flags.
             `--- /dev/null` / `+++ /dev/null` -> None, so is_new / is_deleted. "Binary files " and "GIT binary patch" -> is_binary.
             C-quoted paths: up to 3 octal digits are read as bytes and then UTF-8 decoded, so "a/sp\303\251c.py" becomes "a/spéc.py";
             the a/ and b/ prefixes are stripped. "\ No newline" inside a hunk is skipped without changing the line counts, and outside a hunk it is ignored.
```
A risk next to the claim (it is not one of the listed forms): `cli.py` runs `git diff --no-ext-diff
--no-color -M -U3` and passes no option that fixes the prefixes. The git docs say `diff.mnemonicPrefix` makes `git diff HEAD`
use c/ and w/ prefixes, and `diff.noPrefix` removes prefixes (`config/diff.adoc` L111-128). The parser strips
only `a/` and `b/`. So on a developer machine with that config, the default (no `--range`) mode can produce
wrong paths. CI runners are unlikely to have that config. Channel B could check this.

## C12 — action SHAs are the stated tags

```
claim_id:    C12
verdict:     CONFIRMED
source:      gh api repos/actions/checkout/git/ref/tags/v7.0.1 ; gh api repos/actions/setup-python/git/ref/tags/v7.1.0
source_tier: 1 (GitHub API)
version:     refs as of 2026-10-29
quote:       checkout: "ref":"refs/tags/v7.0.1" ... "sha":"3d3c42e5aac5ba805825da76410c181273ba90b1","type":"commit"
retrieved:   2026-10-29
note:        setup-python refs/tags/v7.1.0 -> 6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 (type commit). Both are lightweight
             tags pointing straight at commits, so no tag-object dereference is needed. The floating v7 tag currently
             points to the same SHAs.
```

## C13 — src/ and hooks/ run on Python 3.9

```
claim_id:    C13
verdict:     CONFIRMED (by reading; no interpreter or parser was run on the project)
source:      src/test_tamper_guard/{__init__,__main__,cli,engine,rules,diffparse}.py, hooks/pretooluse.py
             checked against https://docs.python.org/3.9/ (library/subprocess, dataclasses, functools, typing)
source_tier: project source read against 3.9 docs
version:     Python 3.9
note:        grep found none of: match/case, PEP 604 `X | None`, PEP 585 builtin generics outside annotations,
             f-strings, walrus, zip(strict=), dataclass(slots=/kw_only=), int.bit_count, itertools.pairwise,
             TypeAlias/ParamSpec/TypeGuard, ExceptionGroup/except*, tomllib, parenthesized with-items, or 3.11 regex
             atomic groups/possessive quantifiers. Typing comes from `typing` (List/Optional/Dict/Set/Tuple/Sequence).
             Every stdlib call used exists in 3.9: subprocess.run(capture_output=) is 3.7+,
             dataclass(frozen=True)/field(default_factory, repr, compare), lru_cache(maxsize=), collections.Counter,
             difflib.unified_diff/SequenceMatcher, os.path.*, json, argparse, re.
```
Limits: this is a grep plus a read of 1448 lines, not a parse. Running the CI matrix on 3.9 (Channel B)
is the deciding evidence.

---

## Summary

| ID | Verdict | Main caveat |
|---|---|---|
| C1 | CONFIRMED | Adding `abs` to a bare `approx()` *tightens* it (the default rel is dropped). |
| C2 | CONFIRMED | `xfail(raises=E)` with a different exception still fails; `skipif(False)` does nothing; `--runxfail`. |
| C3 | CONFIRMED | expectedFailure does not cover failures in setUp or other fixture methods. |
| C4 | CONFIRMED | torch: rtol/atol are keyword-only and must be given together. |
| C5 | CONFIRMED | — |
| C6 | (a) CONFIRMED; (b) CONFIRMED for the listed forms | Not matched: `xit.each`, `fit.each`, `xdescribe.each`, `fdescribe.each`, `x*/fit.failing`, one-line tagged-template `.each`. The diff-wide removed-marker counter hides an added marker when the same kind is removed anywhere. |
| C7 | CONFIRMED except the MultiEdit part, which is UNVERIFIABLE | MultiEdit is in no current Claude Code doc or changelog; "ask" from a plugin hook is documented (label `[plugin:<name>]`). |
| C8 | CONFIRMED | plugin.json is optional; managed `allowManagedHooksOnly` can block plugin hooks. |
| C9 | CONFIRMED (a and b) | The escaping rule comes from toolkit source; the docs page does not state it. |
| C10 | CONFIRMED | fetch-depth 0 is enough, but not strictly required. |
| C11 | CONFIRMED (a and b) | `diff.mnemonicPrefix`/`noPrefix` user config would break path prefixes in the default mode. |
| C12 | CONFIRMED | — |
| C13 | CONFIRMED (by reading) | Needs a real 3.9 run to settle. |
