# Prior art

Checked 2026-10-29. Code and docs were read only. Nothing was run.

## MykytaStel/repopilot (24 stars, MIT OR Apache-2.0)

RepoPilot is the closest tool. It is written in Rust and uses tree-sitter. It compares whole
before and after files, not only the changed lines. If either side does not parse, it reports
nothing.

**What it detects:**

- skip, xfail, ignore and todo markers
- focus markers (`.only`, `fit`, `fdescribe`)
- removed tests
- removed or trivial assertions (counted per test)
- JS matcher weakening (`toEqual` becoming `toMatchObject`)
- added lint and type suppressions
- relaxed CI gates
- edits to its own suppression file

**What it does not detect:** we found no handling of these:

- loosened numeric tolerances (`approx`, `rtol`, `toBeCloseTo`)
- changed expected literals
- commented-out tests
- skips that cite an issue (it prints the reason, but does not exempt it)
- a removed feature whose tests are removed with it

**Measured results:** these are its own held-out numbers for v0.25.0, at PR level.

| Detector | Precision | Recall |
|---|---|---|
| test-removed | 3/4 | 3/8 |
| assertions-removed | 3/4 | 3/5 |

The counts are small. The labels were made by the same model that wrote the detectors.

## Other tools

These were found by GitHub search only. We did not read their code.

- `smixs/code-quality` (20 stars): git hooks that block test tampering. It also checks CRAP score and diff coverage.
- `hidevinliu/red-green-mode` (11 stars): exit-code checks for weakened assertions.
- `JeelGajera/OpenInvar` (5 stars): deterministic integrity checks.

## What test-tamper-guard does differently in v0.1

- It detects tolerance loosening, changed expected literals and commented-out tests. These are
  the gaps listed above.
- It down-grades a deleted test when the same diff deletes the code that the test calls.
- It down-grades a skip that cites an issue.
- It reports precision and recall on a held-out fixture set that was written blind to the rules.

## What we took from RepoPilot

- Moves across files are netted out.
- Focus markers count as tampering.
- Results are measured on a held-out set.
- For v0.2: compare whole files when they are available.
