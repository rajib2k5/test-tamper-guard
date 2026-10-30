# test-tamper-guard

test-tamper-guard reads a diff and flags changes that weaken tests instead of fixing the code. Examples are a new skip, a looser tolerance, a deleted test, or an expected value changed to match a bug. A person then looks at the flagged lines before the change merges. The tool does analysis only. It never edits files, never runs tests, and never runs code from your repository. It has no runtime dependencies and needs Python 3.9 or later. It reads Python (pytest, unittest) and JavaScript or TypeScript (jest, vitest) tests.

## What it detects

The tool reports a finding as a rule id, a severity, a file and line, and the changed line.

| Rule id | What it catches | Severity | Down-grade (legitimate case) |
|---|---|---|---|
| `test-deleted` | A removed test, or a deleted test file, with no test of the same name added in the diff. Also one removed case of a `parametrize` or `.each` table (medium). | high | low when the same diff removes the code the test calls (feature removal). Low when one test is removed and one is added in the same change block (rename in place). |
| `skip-added` | An added skip, xfail, `todo`, or focus marker (`it.only`, `fit`, `fdescribe`) in pytest, unittest, or jest. | high | low when the marker or the comment above it names one issue: a URL with `/issues/N`, `/pull/N`, or `/browse/KEY-N`, or `#NN`, `gh-NN`, or `PROJ-12` after a word such as "see" or "tracked in". Low when a `skipif` only compares the Python version, platform, `os.name`, `find_spec`, or `shutil.which` with a real value, or checks that an optional module `is None`. |
| `tolerance-loosened` | A looser `approx`, `rtol`, `atol`, `places`, `delta`, or `toBeCloseTo` digit count. An exact `==` or `toBe` that became approximate. | high | None. A tighter tolerance is not flagged. |
| `expected-changed` | An assert with the same shape in which one literal changed. | medium | low when the same diff changes the code of a function or class that the test names. Comments, docstrings, whitespace, and renamed locals do not count. |
| `assert-removed` | More assertion lines removed than added in a test file, or an assert replaced by a no-op. | medium | None. |
| `assert-weakened` | `assert X == X`, `assert ... or True`, `assert True`, an early `return` in a test, `toEqual` changed to `toMatchObject`, `toThrow('msg')` changed to `toThrow()`, and similar. Not in new files. | medium | None. |
| `test-commented-out` | A test, decorator, or assert that the diff removes and comments out. Also existing test lines wrapped in a block comment. | high | None. |
| `test-config-weakened` | Runner config that drops tests: `--deselect`, `-k`, or `--ignore` in pytest `addopts`; `collect_ignore`; `testPathIgnorePatterns`; `\|\| true` or `--passWithNoTests` on the `test` script. | high | None. |

Docs/DESIGN.md has the full pattern list for each rule.

## Install and use the CLI

```
pip install git+https://github.com/rajib2k5/test-tamper-guard
```

Run `test-tamper-guard` with no arguments to check your staged and unstaged changes (`git diff HEAD`).

| Option | Meaning |
|---|---|
| `--diff FILE` | Read a unified diff from FILE. Use `--diff -` for stdin. |
| `--range A..B` | Check `git diff A B`. |
| `--range A...B` | Check the changes on B since it left A (merge-base form). |
| `--format text\|json\|github` | Output format. The default is `text`. `github` prints workflow annotations. |
| `--fail-on high\|medium\|low\|never` | Exit 1 when a finding has this severity or higher. The default is `high`. |

Exit codes:

| Code | Meaning |
|---|---|
| 0 | No finding at or above `--fail-on`. |
| 1 | At least one finding at or above `--fail-on`. |
| 2 | Usage error or git error. |

Example. A repository has a test file with two tests. Then we loosen an `approx` and add a `skip`:

```
$ git diff   # shortened
-    assert area(2.0) == pytest.approx(12.566, rel=1e-3)
+    assert area(2.0) == pytest.approx(12.566, rel=1e-1)
...
+@pytest.mark.skip
 def test_total():

$ test-tamper-guard
tests/test_calc.py:4: high tolerance-loosened: approx tolerance loosened (rel: 0.001 -> 0.1)
    assert area(2.0) == pytest.approx(12.566, rel=1e-1)
tests/test_calc.py:6: high skip-added: added skip marker pytest.mark.skip without a linked issue
    @pytest.mark.skip
test-tamper-guard: 2 finding(s) (high 2, medium 0, low 0)
$ echo $?
1
```

The same change after a commit, with `--range HEAD~1..HEAD --format github`:

```
::error file=tests/test_calc.py,line=4,title=test-tamper-guard tolerance-loosened (high)::approx tolerance loosened (rel: 0.001 -> 0.1)%0Aassert area(2.0) == pytest.approx(12.566, rel=1e-1)
::error file=tests/test_calc.py,line=6,title=test-tamper-guard skip-added (high)::added skip marker pytest.mark.skip without a linked issue%0A@pytest.mark.skip
```

With `--fail-on never`, the same run prints the same findings and exits 0.

## Claude Code hook (opt-in)

The hook is off until you install and enable the plugin. Nothing in this repository writes to `~/.claude` or to any `settings.json`.

```
/plugin marketplace add rajib2k5/test-tamper-guard
/plugin install test-tamper-guard@test-tamper-guard
```

After you enable it, a `PreToolUse` hook runs on every `Write`, `Edit`, and `MultiEdit` of a test file. It builds the proposed new file in memory, diffs it against the current file, and runs the rules. If it finds a problem at the set level, it asks you to confirm the edit. By default it only asks. It never blocks.

The hook needs `python3` on your PATH. If the hook crashes, it fails open: your session goes on. One case is different. If the check of a test file runs out of time, the hook asks you to confirm, and the reason says that the guard could not finish. A hook that times out would let the edit through unchecked.

| Variable | Values | Default |
|---|---|---|
| `TEST_TAMPER_GUARD_MODE` | `ask`, `deny`, `warn` (print to stderr, no prompt), `off` | `ask` |
| `TEST_TAMPER_GUARD_LEVEL` | Lowest severity to report: `high`, `medium`, `low` | `medium` |
| `TEST_TAMPER_GUARD_BUDGET_S` | Seconds for one check (the hook timeout is 10 s). `0` turns the limit off. Works on Linux and macOS only. | `7` |

To turn it off, run `/plugin disable test-tamper-guard`, or set `TEST_TAMPER_GUARD_MODE=off`.

The hook sees only the Write, Edit, and MultiEdit tools. It does not see edits made through Bash, such as `sed -i` or a heredoc. For those edits, run the CLI or use the GitHub Action.

## GitHub Action

```yaml
name: test-tamper-guard
on: pull_request

permissions:
  contents: read

jobs:
  guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
      - uses: rajib2k5/test-tamper-guard@main
        with:
          fail-on: high
```

`fetch-depth: 0` is required. The Action needs both commits of the range. `@main` follows the branch. Pin a commit SHA instead.

Inputs: `base` and `head` (default: the pull request base and head SHAs), `fail-on` (`high`, `medium`, `low`, `never`; default `high`), and `python` (default `python3`, 3.9 or later). The Action runs `--range base...head --format github`, so findings show as annotations. The Action fails the check only as `fail-on` says. On a push event there is no base. Then the Action checks the last commit only (`head~1...head`). If that commit is a root commit in a full clone, the Action prints a notice and passes. If the clone is shallow and the parent or base commit is missing, the Action fails with exit 2 and tells you to set `fetch-depth: 0`.

## Measured results

We measured the rules on fixture diffs (a tamper fixture must be flagged at medium or above; a legitimate fixture must not be). The raw output is in `docs/eval/`.

| Set | Tamper detected | Legitimate flagged | How to read it |
|---|---|---|---|
| Dev set (45 tamper, 24 legit) | 45/45 (100.0%) | 2/24 (8.3%) | Optimistic. We wrote these fixtures with the rules. The two flagged ones are a cost of stricter down-grades (see Known limits). |
| Held-out set, first run | 23/25 (92.0%) | 2/16 (12.5%) | The first measurement. A separate author wrote the fixtures without the rules. |
| Held-out set, after fixes | 24/25 (96.0%) | 1/16 (6.2%) | Contaminated. The fixes used the misses of the first run. |

The fixture author worked blind to the rules. The rule author says they did not read the fixtures. File timestamps cannot prove this. Treat the first-run row as the honest number and the other two as upper bounds.

Real repository history. We ran the engine on the last commits of five public repositories and read every flagged commit (`docs/eval/history-v0.1.txt`):

| Repository | Commits flagged (medium or high) |
|---|---|
| click | 7/79 (8.9%) |
| pydantic-settings | 7/100 (7.0%) |
| ky | 6/100 (6.0%) |
| httpx | 10/100 (10.0%) |
| vitest | 7/100 (7.0%) |
| Total | 37/479 |

We judged 2 of the 37 flagged commits to be likely real problems: click c3535905 deletes the only test of multi-line help while the code for it stays, and httpx eeb5e3c2 deletes a test with no code change. We judged the other 35 to be false positives. On ordinary maintainer history, about 6 to 10 % of commits get a medium or high finding that a person must dismiss. Causes: an `expected-changed` finding where the test does not name the changed function, or the input changed too (17); tests deleted or renamed across hunks, or a removed feature (9); skip gates that the rules do not recognise (6), three of them `skipif(yaml is None)` gates that a stricter rule no longer accepts; and net assert count after a rewrite or `expect.soft` (3). ky uses AVA, which the tool does not support, so ky measures only `test-deleted`.

Reproduce:

```
python3 scripts/eval_fixtures.py fixtures            # dev set
python3 scripts/eval_fixtures.py fixtures-holdout    # held-out set (current rules: the "after fixes" numbers)
git clone --depth 200 --no-checkout <repo-url> <clone>
python3 -I scripts/eval_history.py <clone> -n 100    # real history
```

The first-run held-out numbers need the rules as they were before the fixes. They are frozen in `docs/eval/holdout-v0.1-first-run.txt`.

## Validation

We checked 13 claims about the libraries and platforms the tool depends on. Two independent checks ran for each claim: one read the official documentation and one probed the runtime. The verdict is in `docs/validation/verdict.md`.

Accepted by both checks: the `approx`, `rtol`, `atol`, `places`, `delta`, and `toBeCloseTo` semantics; pytest skip and xfail; jest skip and focus forms (the 13 forms the tool lists); git diff header parsing; the pinned action SHAs; Python 3.9 support (491 tests passed on CPython 3.9.25).

Not proven:

- Claude Code shows the "ask" prompt for this plugin's hook. The check could not run Claude Code. The field names match the documentation and the SDK types.
- `MultiEdit` input is not in the Claude Code documentation. The hook handles it and does no harm if it is never sent.
- Plugin hooks load only when the plugin is enabled, and `${CLAUDE_PLUGIN_ROOT}` expands at runtime. We confirmed this from the documentation only.

Each of these three items needs a live run in Claude Code.

Confirmed by a live run: the Action ran on a GitHub runner on this repository's PR #1. It created 10 annotations with the correct file, line, and rule.

## Known limits

- The rules read diff lines. They do not parse code (no AST). A multi-line call, such as an `approx(` split over lines, can be missed. The rules skip docstrings, block comments, and multi-line template literals. But if a string opens and closes outside the hunk, its lines still look like code.
- Stricter down-grades have a cost. A changed module constant (`TAX_RATE = 0.10`) does not down-grade `expected-changed`. A ticket key without a word such as "see" (`// WEB-1182: ...`) does not down-grade `skip-added`. Two dev fixtures are flagged for these reasons. A skip condition is an environment gate only in simple forms. These forms stay high: `not` over a check, the same check used twice (such as a version range), a version compared with `==` or `!=`, `startswith` with a partial name (`"win"`), and `X is None` when the diff does not set `X = None`.
- `assert-weakened` does not see a pytest assert made weaker in place, such as `== 4` changed to `is not None` or `>= 0`. It does not count `expect.soft` as an assert.
- A tolerance set through a variable is not seen.
- Tests moved or renamed across hunks look like a deletion. This caused most of the 9 deletion false positives above.
- Speed. The target is under 1 s for a 5,000-line diff, and the tool takes 0.06 s. The target for 500,000 diff lines is under 5 s, and the tool takes 6.92 s, so it misses that target. Other measurements: 50,000 lines in 0.66 s, and one 100,000-line hunk in 2.12 s. These are CPU times on one busy machine. In the hook, a very large edit can take longer than the time budget. Then the hook asks you to confirm. The hook does not analyse a test file when its old or new content is over 2 MB. It asks you to confirm that edit too.
- An agent that knows the rules can evade them. For example, it can put a tolerance in a variable or split a call over lines.
- An issue link is self-attested. An agent can write a link to an issue that does not exist, and the skip then gets low severity. Only a link on the marker or on a new comment line directly above it counts.
- On a push, the Action checks only the last commit. A push of several commits checks only the newest one.
- On a contrived, very large `conftest.py` diff, one check (`_in_func`) takes quadratic time. In the hook, the time budget then turns the edit into an ask.
- The tool is a review aid. It reports suspicious changes. It does not prove that a change is wrong or that a change is safe.
- Languages: Python and JavaScript or TypeScript only. No Go, Rust, JUnit, or RSpec.

## Prior art

The closest tool is [RepoPilot](https://github.com/MykytaStel/repopilot). It uses tree-sitter on whole files. We found no handling in it of loosened tolerances, changed expected literals, commented-out tests, or skips that cite an issue. We took these ideas from it: net out moves across files, count focus markers, and measure on a held-out set. For v0.2 we plan to compare whole files when they are available. See `docs/PRIOR_ART.md` for the details. That file also lists tools we found by search only and did not read.

## Development

```
uv run --with pytest pytest -q
python3 scripts/eval_fixtures.py fixtures
python3 scripts/build_dev_fixtures.py --check
```

The design is in `docs/DESIGN.md`.

## Licence

MIT. See `LICENSE`. Copyright 2026 Rajib Bahar.
