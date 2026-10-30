# test-tamper-guard — design (v0.1)

## Problem

AI coding agents sometimes make a red suite green by weakening the tests, not by fixing the code:
they delete a test, add `skip`/`xfail`, widen a tolerance, change the expected value to the value the
bug produces, drop an assert, or comment a test out. These diffs look like normal edits in review.

The guard reads a diff and flags these patterns, so a person looks at them before they merge.

## Constraints

- Analysis only. The guard never edits files, never runs tests, never runs code from the repo.
- No runtime dependencies (Python 3.9+ standard library only). It must run in a Claude Code hook
  within the hook timeout (target: under 1 s for a 5,000-line diff) and in a GitHub Action with no
  install step.
- The Claude Code hook is opt-in: it is active only when the user installs the plugin. Nothing in
  this repo writes to `~/.claude`, to any `settings.json`, or registers a hook at install time.
- Fail open in the hook: a crash in the guard must not block the user's session.
- v0.1 languages: Python/pytest (and `unittest` asserts), JavaScript/TypeScript/jest (and vitest,
  which uses the same API).

## Non-goals (v0.1)

- Proving a test change is wrong. The guard reports *suspicious* changes; a person decides.
- Full parsing (AST) of either language. v0.1 works on diff lines, so the same engine serves stdin
  diffs, commit ranges and the hook.
- Mutation testing, running the suite, coverage diff.
- Other frameworks (Go, Rust, JUnit, RSpec). The rule table is per framework, so these are additive.
- Blocking merges by itself. The Action fails the check only when the user sets `fail-on`.

## Alternatives considered

| Option | How it works | How it fails | Cost |
|---|---|---|---|
| A. Line rules on unified diff hunks (**chosen**) | Parse the diff into files → hunks → removed/added lines; pair removed and added lines; regex rules per framework | Multi-line constructs (an `approx(` call split over lines, a 3-line `it(` header) can be missed; string/comment content can false-match | ~1 ms per 1k diff lines; zero deps |
| B. Before/after AST comparison | Fetch full old/new files, parse (Python `ast`; JS needs a parser dep), diff test functions and assert nodes | Needs full files (not available for a raw stdin diff); JS needs `@babel/parser` or tree-sitter (a dependency, a build step); breaks on syntax errors mid-edit | Better precision on Python; dependency + 2 code paths |
| C. Run the suite before/after and compare collected test IDs and assert counts | Ground truth on "tests removed/skipped" | Runs untrusted repo code in the hook (security), slow (seconds to minutes), cannot see tolerance or literal changes | Too slow for a hook; out of the analysis-only constraint |

**Recommendation: A for v0.1.** One engine, one input format, no dependencies, works in all three
entry points. What would change my mind: held-out recall on multi-line constructs below ~70 %. Then
add B for Python only (stdlib `ast`), behind the same `Finding` interface.

## Interface contract

```
Finding = { rule: str, severity: "high"|"medium"|"low", path: str, line: int (new-side line,
            or old-side line for deletions), message: str, evidence: str }
```

- `analyze_diff(diff_text: str, config: Config) -> list[Finding]` — pure function, no I/O.
- CLI `test-tamper-guard`:
  - `--diff FILE` or `-` (stdin) — read a unified diff.
  - `--range A..B` — run `git -c core.quotePath=true diff --no-ext-diff --no-color --src-prefix=a/
    --dst-prefix=b/ -M -U3 A B` (argument list, no shell). The fixed prefixes and quoting mean user
    config (`diff.noPrefix`, `diff.mnemonicPrefix`, `core.quotePath=false`) cannot change the paths.
  - `--range A...B` — the same with git's merge-base form (`git diff A...B`: the changes on B since
    it left A). Each side is rejected if it starts with `-`.
  - default: `git diff HEAD` (staged + unstaged changes).
  - `--format text|json|github`; `--fail-on high|medium|low|never` (default `high`).
  - Exit codes: `0` no finding at or above `fail-on`; `1` findings at or above `fail-on`;
    `2` usage or git error.
- Claude Code hook `hooks/pretooluse.py`: on `Write`/`Edit`/`MultiEdit` of a test file, build the
  proposed new content (CRLF and LF are normalised to LF before `old_string` is matched), make a
  unified diff old→new with `difflib`, run `analyze_diff`. On a finding
  of severity ≥ `TEST_TAMPER_GUARD_LEVEL` (default `medium`) return
  `permissionDecision: "ask"` with the findings as the reason. Never `deny` unless
  `TEST_TAMPER_GUARD_MODE=deny`. `TEST_TAMPER_GUARD_MODE=off` disables it. Reading, diffing and
  analysing run under a time budget (`TEST_TAMPER_GUARD_BUDGET_S`, default 7 s, under the 10 s hook
  timeout; `SIGALRM`, so POSIX only; `0` turns it off). When the budget runs out on a test file, the
  hook returns `ask` with a reason that says the guard could not finish (also in `deny` mode; `warn`
  prints it to stderr; `off` does nothing): a hook that times out would let the edit through
  unchecked. Any other error still fails open.
- GitHub Action `action.yml` (composite): runs the CLI on `base...head` of the PR (from the merge
  base, so commits that landed on the base branch after the PR branched are not reported) with
  `--format github` (workflow annotations) and the user's `fail-on`. On a push event `base` is empty:
  the Action checks the last commit (`head~1...head`), or prints a notice and passes when `head` has
  no parent.

## Rules

Each rule has an id, a severity, and a per-framework pattern set.

| id | Detects | Severity | Down-grade (legitimate case) |
|---|---|---|---|
| `test-deleted` | A removed test definition (`def test_*`, `it(`/`test(`), or a deleted test file, with no definition of the same name added anywhere in the diff | high | The test body references a function/class whose definition the same diff removes from non-test code (feature removal) → low. In one hunk exactly one test definition is removed and exactly one is added in the same change block (renamed and rewritten in place) → low; its asserts still count for `assert-removed` |
| `test-deleted` (case) | A removed line that is one case of a `@pytest.mark.parametrize(...)` list or an `it.each([...])`/`test.each`/`describe.each` table, with no added line paired to it and no added table row in the same change block, while the table's header stays | medium | — |
| `skip-added` | Added `@pytest.mark.skip/skipif/xfail`, `pytest.skip(`, `pytest.xfail(`, `@unittest.skip*`, `it.skip`/`test.skip`/`describe.skip`, `xit`/`xtest`/`xdescribe` (also `.each`, `.failing`), `test.todo`, `it.failing`, and focus markers `it.only`/`fit`/`fdescribe` (also `.each`; they silence every other test). Removed markers cancel added ones of the same kind only in the same file, or when the same test moved with its marker | high | The marker, its continuation lines, or an added (`+`) comment line directly above it names one issue (a link on a context comment that was already there does not count): a URL whose path holds `/issues/N`, `/pull/N`, `/-/issues/N` or `/browse/KEY-N`; or, after a tracker word (issue, bug, see, tracked in, ticket, fixes, closes, refs, blocked by/on), `#NN`, `gh-NN` or a `KEY-NN` ticket key (two or more capitals, two or more digits, not an encoding/standard/placeholder such as UTF-8, PEP-8, TODO-1) → low. A `skipif`/`skipIf`/`skipUnless` whose condition (parsed as one Python expression; nothing is run) is made only of environment probes compared with real values → low: `sys.version_info` (or `[:2]`) with `<`, `<=`, `>` or `>=` against `(3, N)`, N ≥ 1; `sys.platform` `==`/`!=`/`.startswith(` an exact known value (linux, darwin, win32, cygwin, emscripten, wasi, aix, sunos5, freebsd/openbsd/netbsd with an optional release number); `os.name` against posix/nt/java; `platform.system()` against Linux/Darwin/Windows/Java (in the case `.lower()`/`.upper()` gives); `sys.implementation.name` against a known name; `find_spec(...)` / `shutil.which(...)` `is None`, `is not None` or under `not`; `X is None` / `X is not None` only when the file's diff (any side, context included) holds `X = None` or `X = pytest.importorskip(`. Not gates: bare probes, `or True`, unknown or partial platform names (`linux2`, `"win"`), `==`/`!=` on version tuples, `[0]`, `[:1]`, major ≠ 3, `(3, 0)`, `not` over a gate, and an `and`/`or` that uses one probe twice (`X or not X`; this also makes a version range high) |
| `tolerance-loosened` | A paired change where `approx(rel=/abs=)`, `rtol=`, `atol=`, `places=`, `delta=`, `toBeCloseTo(x, digits)` got looser, or an exact `==`/`toBe`/`toEqual` became approximate | high | — (tightening is not flagged) |
| `expected-changed` | A paired assert line whose shape is identical but one literal (number, string, bool, None) changed | medium | The same diff changes a non-test source file, that module is plausibly under test (its stem appears as a word in the test file's diff text, or the test file is named `test_<stem>`/`<stem>_test`/`<stem>.test.*`/`<stem>.spec.*`), and the change touches a function/class/const whose name appears in the test file's diff text. The touched lines must be code: not comments, docstrings or whitespace, and not only a rename of parameters or locals (compared with locals numbered by first use). The owner of a changed line is the nearest less-indented definition in the hunk, or git's hunk-header function → low |
| `assert-removed` | In a test file, more assertion lines removed than added (net loss), or an assert replaced by a no-op | medium | — |
| `assert-weakened` | In an existing test file (not a new file). When added: `assert X == X` / `expect(X).toBe(X)` (same expression both sides, a name, attribute chain or call; not a list/object literal, `new X`, or `X.from([...])`, which are matcher self-tests), `assert ... or True`, `if False:`/`if (false)` wrapping an assert. When it replaces a stronger form in the same change block: `assert True`/`expect(true).toBe(true)` for a real assert; a bare `return` added as the first statement of a test; `try:` around a moved assert with `except AssertionError: pass`; `toEqual`/`toStrictEqual`/`toBe` → `toMatchObject`/`toBeDefined`/`toBeTruthy`; `.not` added to an existing expect with the same subject and matcher; `toThrow('msg')`/`toThrow(Err)` → `toThrow()`; `pytest.raises(SpecificError)`/`assertRaises` → `Exception`/`BaseException`; `assertEqual(x, v)` → `assertTrue(x)`/`assertIsNotNone(x)` | medium | — |
| `test-commented-out` | An added comment line whose uncommented text is a test definition, decorator, or assert that the same diff removed; or existing test lines wrapped in an added block comment / triple-quoted string (both delimiters added, the opening one starting a bare string statement) | high | — |
| `test-config-weakened` | Runner config (not test files) that drops tests: `--deselect`, `-k`, `--ignore`, `--ignore-glob` added to pytest `addopts` in `pytest.ini`/`setup.cfg`/`tox.ini`/`pyproject.toml`; `collect_ignore`/`collect_ignore_glob` in `conftest.py`; `pytest_collection_modifyitems` that removes or deselects items; new `testPathIgnorePatterns`/`modulePathIgnorePatterns` entries in `jest.config.*`/`package.json` (other than `node_modules`); `\|\| true` / `--passWithNoTests` added to the `"test"` script | high | — |

"Paired" means: inside one hunk, a run of `-` lines followed by a run of `+` lines; pair them by
order, with a similarity check (normalised-token ratio ≥ 0.6) so unrelated lines do not pair.

## Failure modes

- **Malicious / adversarial input**: the diff is untrusted. Regexes are linear (no nested
  quantifiers on overlapping classes, no `\s*(.*?)\s*$`-style tails); a line over 10,000 chars is
  truncated before matching. String literals are found by a scanner that stops trying a quote kind
  once one of its strings runs to the end of the line unclosed (`STR_RE.finditer` was quadratic on
  `'\'\'\'...`). Timing tests in `tests/test_adversarial.py` use CPU time with generous bounds. The CLI
  passes git arguments as a list (no shell); `--range` is rejected if it starts with `-`.
- **Path names in diffs** with spaces, quotes, `\t`, or `/dev/null` are parsed per the git diff
  header format; unparseable headers are skipped, not fatal.
- **Renames/moves**: git `-M` marks renames; a test name removed in one file and added in another
  is a move, not a deletion.
- **Hook on a file not yet on disk** (Write of a new file): old content is empty, nothing to flag.
- **Hook on a test file over 2 MB** (old or new content): the guard does not analyse it and asks,
  even in deny mode (warn: stderr; off: nothing). Before review 3 it gave no decision, so a padded
  file let every later edit through unchecked. A non-test file stays silent.
- **Action on a shallow checkout**: when the parent (push) or base (pull request) commit is missing
  and `git rev-parse --is-shallow-repository` is true, the step fails with exit 2 and an `::error::`
  that asks for `fetch-depth: 0`. Only a root commit in a full clone passes with a notice.
- **Hook on `Edit` whose `old_string` is not found**, or is found more than once without
  `replace_all`: Claude Code will reject the edit itself; the hook returns no decision. A CRLF file
  is matched after normalising both the file and the edit strings to LF.
- **Docstrings, block comments, template literals**: each side of a hunk (old: context + removed
  lines; new: context + added lines) is scanned in order, and the parts of multi-line triple-quoted
  strings, JS block comments and multi-line template literals are blanked before the def / assert /
  skip / table rules run. Values (`expected-changed`, `tolerance-loosened`) are compared with JS
  template literals kept, since an inline snapshot is an expected value. When the hunk starts inside
  such a string, its opener is not in the diff: a closing `"""` with only prose before it and only
  closing brackets after it (or a lone `"""` when the side has an odd number of delimiters and the
  line above opens no block), a `*/` before any `/*`, or a lone `` ` `` followed only by closing
  brackets marks the lines above it as string content. test-commented-out reads the raw lines: code
  is reported as commented out only when both delimiters around it are added lines.
- **Moved skipped test**: a skip marker removed in file A and added in file B is cancelled only when
  it belongs to the same test name (the test moved with its marker).
- **Huge diffs** (100× scale): linear in lines; 500k diff lines target < 5 s. Measured after
  review round 2 (CPU time, `scratchpad/perf2.py`, one shared machine with load average 15-25, so
  ±10 %): 5k lines 0.06 s, 50k 0.66 s, 500k 6.92 s (the target is missed by about 1.9 s), one
  100k-line hunk 2.12 s. The round-1 engine on the same machine in the same session: 0.07 s, 0.63 s,
  6.71 s, 2.08 s. Every module-level regex stays under 50 ms CPU on 10,000-char probe lines
  (`tests/test_regex_time.py`); the per-row table check is done once per hunk (`TableContext`), so
  100 removed rows under a 10,000-char opener line take milliseconds, not 18 s. The hook's
  `difflib` diff is not linear: rewriting a 20,000-line test file took about 7 s in `difflib`
  alone, which is what the hook time budget is for.
- **Binary diffs**: skipped.

## Known limits (v0.1)

- **Strings whose delimiters are both outside the hunk.** With 3 lines of context, a docstring or
  block comment that opens and closes outside the hunk cannot be seen; its lines are read as code
  (a `def test_example():` removed from the middle of a long docstring still reads as a deleted test).
- **`assert-weakened` limits.** Pytest plain-assert weakening is not detected: `== v` → `is not None`,
  `isinstance(...)`, `>= 0`, or a bare call (`assert g(2)`). Self-comparison of a constructed value
  (`[1, 2] == [1, 2]`, `expect(new X())...`) is not flagged, by design. `.not` added is flagged only
  for the same subject and matcher, and the single-old / single-new fallback pairing can still match
  a `.not` in a new test with an old expect of the same subject. Not run on new files.
  `expect.soft(...)` is not counted as an assertion.
- **Down-grades the rules cannot see through.** A test deleted while the diff renames the source
  function it called stays low (feature-removal down-grade). A module-level constant change
  (`TAX_RATE = 0.10`) does not down-grade `expected-changed`, because no function the test names was
  touched (dev fixture legit/08 is flagged medium for this reason). A ticket key with no tracker word
  (`// WEB-1182: ...`, dev fixture legit/15) no longer down-grades.
- **AVA** (`t.is`, `t.deepEqual`, used by ky and got) is not a supported framework: only
  `test-deleted` applies to it.
- **Push events** in the Action check only the last commit.
- **Issue links are self-attested.** Nothing checks that the linked issue exists; an agent can
  write one to get low severity.
- **`_in_func` is quadratic** on contrived large `conftest.py` diffs (many lines with no enclosing
  def); in the hook the time budget turns this into an ask.

v0.2 items: pytest plain-assert weakening (`== v` → `is not None`, `isinstance`, `>= 0`, bare
call); AVA support; push-event refinements (the whole pushed range from `github.event.before`);
the delete-test + rename-source-function down-grade (today low); module-level constants as touched
definitions for `expected-changed`.

## Blast radius and rollback

The hook can only *ask*. Worst case for a false positive: one extra prompt. Rollback: disable the
plugin (`/plugin disable test-tamper-guard`) or set `TEST_TAMPER_GUARD_MODE=off`. The Action can only
fail a check; remove the workflow step to roll back.

## How we know it works (SLI)

Precision and recall on two fixture sets:

1. **dev set** (`fixtures/`): ≥ 20 seeded-tamper diffs and ≥ 10 legitimate diffs, written alongside
   the rules.
2. **held-out set** (`fixtures-holdout/`): written by a separate agent that did not see the rules,
   after the rules were frozen. It was measured honestly once, before any fix: that first run is
   frozen in `docs/eval/holdout-v0.1-first-run.txt` and is the honest number (the dev-set number is
   optimistic by construction). The v0.1 review round then read the held-out fixtures and fixed two
   of their misses (legit/13 link on the comment line above, tamper/03 parametrize case), so every
   later run, including `docs/eval/holdout-v0.1-after-fixes.txt` (re-run after review round 2), is
   contaminated: an upper bound, not a held-out measurement. A new held-out set is needed for the
   next honest number.

`scripts/eval_fixtures.py` prints, per rule and overall: recall on tamper fixtures twice (detected by
any rule at ≥ medium; detected by one of the fixture's expected rules at ≥ medium), false-positive
rate on legitimate fixtures, precision. `scripts/eval_history.py REPO [-n N]` runs the engine over the
last N first-parent non-merge commits of a real repo (`git diff C^ C`, no repo code run) and prints
the commits flagged at ≥ medium: a false-positive measure on real history.

## Increments

1. Diff parser + `Finding` + CLI on stdin (expand).
2. Rules one by one, each with fixtures, test-first.
3. Hook + plugin manifest; Action + workflow.
4. Held-out evaluation; README with the measured numbers.
5. Later (v0.2): Python `ast` mode when full files are available; more frameworks.
