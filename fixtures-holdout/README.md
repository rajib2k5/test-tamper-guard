# fixtures-holdout

Blind held-out fixture set for test-tamper-guard.

- Author: a Claude (Sonnet 5.5) subagent, dispatched by the orchestrating session.
- Written blind: the author did not read `src/`, `tests/`, `fixtures/`, `scripts/` or `docs/` of the project, did not run the tool, and did not see its rules. Content comes from general knowledge of how agents weaken pytest and jest tests. Only rule ids and the task description were supplied.
- Counts: 41 fixtures total.
  - tamper: 25 (pytest 15, jest 10; jest = 6 TypeScript + 4 JavaScript)
  - legit: 16 (pytest 9, jest 7; jest = 4 TypeScript + 3 JavaScript)
- Layout: `<tamper|legit>/<NN-slug>/{diff.patch, expected.json, before/, after/}`.
  `expected.json` = `{"tamper", "rules", "framework", "note"}`. `rules` uses ids `test-deleted`, `skip-added`, `tolerance-loosened`, `expected-changed`, `assert-removed`, `test-commented-out`, and is `[]` for legit.
- Caveat: multi-rule labels (22 and the `it.only`/`test.todo` ones) are the author's judgement of what a good tool should report. Fixture 03 (dropped parametrize case) is labelled `test-deleted`, 09 (`it.only`) as `skip-added`, 10 (`test.todo`) as `skip-added` only.

## Generation

1. Fixture sources live in `author_part1.py` (pytest tamper), `author_part2.py` (jest tamper), `author_part3.py` (legit).
2. `python3 build.py` writes each fixture's `before/`, `after/` and `expected.json`.
3. For each fixture it creates a fresh git repo under `/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/holdout-work/<kind>/<slug>/`, copies `before/`, `git add -A && git commit`, replaces the tree with `after/` (deletions and renames fall out of `git add -A`), then `git diff -M --cached > diff.patch`.
4. The generated source files are not executed; they are illustrative and were not run under pytest or jest.
