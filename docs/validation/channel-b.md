# Channel B — runtime audit (empirical probes only)

Auditor: Channel B subagent. Evidence source: probe execution only. No documentation, changelog or web
page was read. `channel-a.md` was not read. Runtime probes against GitHub (`git ls-remote`, `gh api`) were
used for C12, as permitted. Locally installed SDK type definitions and strings in the installed `claude`
binary were inspected for C7/C8, as permitted by the charter; this is static evidence, not runtime.

Work directory: `/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/`
(env pin: `env-pin.txt` there; full pin reproduced at the end of this file).

Deviation from runtime-audit.md section 4: probes ran without the `env -i`/`unshare --net` wrapper
(C12 needs network; the others ran in throwaway scratch dirs and repos). Bytecode was disabled for every
mutation run (`python3 -B` / `PYTHONDONTWRITEBYTECODE=1`, plus `rm -rf src/test_tamper_guard/__pycache__`).

Recording note: every block is `$ (cwd=...) <exact command>` / verbatim combined stdout+stderr / `rc=`.
Where the command ends in `| tail`, the rc is the pipeline's rc unless the command says `exit ${PIPESTATUS[0]}`.
In c1.log the first block's rc=0 is tail's rc (the pytest run had 3 failures); the later blocks have no pipe.

## Verdicts

| ID | Verdict | Measured |
|---|---|---|
| C1 | CONFIRMED | `pytest.approx` signature `(expected, rel=None, abs=None, nan_ok=False)` (pytest 9.2.0). 1.001 vs 1.0: default FAIL, rel=1e-4 FAIL, rel=1e-2 PASS, abs=1e-4 FAIL, abs=1e-2 PASS, rel+abs together accepted. Larger rel/abs is looser. |
| C2 | CONFIRMED | Failing `assert 1 == 2`: base rc=1; `@pytest.mark.skip`, `@pytest.mark.skipif(True, reason=)`, `@pytest.mark.xfail`, `pytest.skip()`, `pytest.xfail()` each give rc=0 (skipped / xfailed). |
| C3 | CONFIRMED | Signature `(self, first, second, places=None, msg=None, delta=None)` exactly (3.12.13). 1.0 vs 1.001: default places FAIL, places=4 FAIL, places=2 PASS, delta=1e-4 FAIL, delta=1e-2 PASS. `skip`, `skipIf(True)`, `skipUnless(False)`, `expectedFailure` each turn rc=1 into rc=0. |
| C4 | CONFIRMED (with a note) | numpy 2.5.4 signature `(actual, desired, rtol=1e-07, atol=0, ...)` exactly; torch 2.15.0+cpu `assert_close(actual, expected, *, ..., rtol=None, atol=None, ...)`. Larger rtol/atol looser for both (tight FAIL, loose PASS). Note: in torch, `rtol`/`atol` are keyword-only and must be given together; `rtol` alone raises `ValueError: Both 'rtol' and 'atol' must be either specified or omitted`. |
| C5 | CONFIRMED | jest 30.5.2: diff 0.001 — numDigits 4 FAIL, 3 FAIL, 2 PASS, default PASS; diff 0.01 — default FAIL, numDigits 1 PASS. Default behaves as 2 (passes 0.001, fails 0.01, which brackets the 0.005 threshold); smaller numDigits looser. |
| C6 | CONFIRMED | jest: base failing test rc=1; `it.skip`, `test.skip`, `describe.skip`, `xit`, `xtest`, `xdescribe`, `test.todo`, `test.failing` each rc=0. Focus: base with failing sibling rc=1; `it.only`, `test.only`, `fit`, `fdescribe`, `describe.only` each rc=0 with sibling `pending` (not run). Engine: on real `git diff` patches adding each of the 13 markers, every one reports `skip-added` at `high` (engine rc=1); a control diff (title rename) gives no finding. Falsifier: removing `"only"` from `JS_MARKERS` made `it.only`, `test.only`, `describe.only` MISS (probe rc=1); restored, sha256 OK, probe rc=0. |
| C7 | UNVERIFIABLE | Claude Code cannot be run in this audit (`claude --version` = 2.1.296 only). Static evidence from installed `@anthropic-ai/claude-agent-sdk` 0.3.195 `.d.ts` (bundled under `cline`, not tied to CLI 2.1.296): `PreToolUseHookInput` has `tool_name`, `tool_input`, `tool_use_id`, `hook_event_name`, plus base `cwd`; `FileWriteInput {file_path, content}`; `FileEditInput {file_path, old_string, new_string, replace_all?}`; `PreToolUseHookSpecificOutput {hookEventName:'PreToolUse', permissionDecision?, permissionDecisionReason?, ...}`; `HookPermissionDecision = 'allow'|'deny'|'ask'|'defer'`. `MultiEdit` does not appear in either `.d.ts` (0 matches) but the string occurs 10 times in the CLI binary. The behavioural part (exit 0 + stdout JSON makes Claude Code ask/deny) was not exercised. |
| C8 | UNVERIFIABLE | Plugin install/enable and `${CLAUDE_PLUGIN_ROOT}` expansion need a running Claude Code. Only static signal: the string `CLAUDE_PLUGIN_ROOT` occurs 62 times in the installed binary. |
| C9 | CONFIRMED for the CLI half; UNVERIFIABLE for the GitHub half | Real git diff on `tests/a,b:c/test_pct.py` adding a skip whose reason contains `100%`: `--format github` output is byte-identical to escaping derived from the claim text (`file=tests/a%2Cb%3Ac/test_pct.py`, `100%25`, `%0A` between message and evidence, one physical line). Direct call: `escape_data("a%b\rc\nd") == "a%25b%0Dc%0Ad"`, `escape_property("x:y,z%\r\n") == "x%3Ay%2Cz%25%0D%0A"`, `escape_data("%0A") == "%250A"` → all True. A CRLF test file yielded no raw `\r` in output. Falsifier: removing the `,`→`%2C` replace made the probe FAIL (rc=1); restored, sha256 OK, rc=0. That GitHub turns these lines into annotations was not observed (no runner). |
| C10 | UNVERIFIABLE (one sub-part supported locally) | `act` not installed; no runner, so `$GITHUB_ACTION_PATH` and `github.event.pull_request.*.sha` were not observed. Local analogue for the fetch-depth sub-claim: in a `git clone --depth=1` clone, `git diff BASE HEAD` → `fatal: bad object`, rc=128, and the CLI `--range BASE..HEAD` → rc=2 with `git diff failed`; in a full clone both succeed (rc=0). |
| C11 | CONFIRMED | Seven real repos (`core.quotePath=true`), `git diff --no-ext-diff --no-color -M -U3 HEAD~1 HEAD`. Headers seen: `rename from/to` (82% and 100%), `new file mode` + `--- /dev/null`, `deleted file mode` + `+++ /dev/null`, `Binary files ... differ`, `"a/tests/test_sp\303\251c.py"`, `\ No newline at end of file` (×2). Parser gives the expected (old_path, new_path, is_new, is_deleted, is_rename, is_binary) on all 7; CLI `--range` never crashed (rc 0 or 1, JSON output) and reported paths `test_new.py`, `test_gone.py`, `tests/test_spéc.py`, `test_nl.py` with the right line numbers; the no-newline markers were not parsed as content. Falsifiers: octal→decimal in `_unquote` killed nonascii; `Binary` branch killed binary; all-sites `is_rename/is_new/is_deleted = False` killed rename+rename100 / new / deleted; no-newline marker parsed as `+` line killed nonewline. Single-site mutants of the `rename from`, `new file mode`, `deleted file mode` branches SURVIVED: the parser detects these states redundantly (`rename to`, `---/+++ /dev/null`). All restores sha256 OK. |
| C12 | CONFIRMED | `git ls-remote`: `3d3c42e5aac5ba805825da76410c181273ba90b1 refs/tags/v7.0.1` (actions/checkout), `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 refs/tags/v7.1.0` (actions/setup-python). No `^{}` peeled entry: lightweight tags; `gh api .../git/ref/tags/...` gives `object.type=commit` with the same SHAs. Discrimination: sibling `v7.0.0` tags resolve to different SHAs (`9c091bb...`, `5fda3b9...`). |
| C13 | CONFIRMED (bounded by coverage) | CPython 3.9.25 + pytest 8.4.2, run from the project dir: `168 passed in 7.39s` (rc=0). All `src/` and `hooks/` files compile under 3.9 (bad=0). Coverage under 3.9: 86% total; `hooks/pretooluse.py` shows 0% in-process because the tests run it as a subprocess with `sys.executable` (19 hook tests pass on 3.9). A 3.10+ API on a line no test executes would not be caught. Falsifier (on a copy): appending `def _probe_310(a: str \| None)` gives `TypeError: unsupported operand type(s) for \|` and rc=2 on 3.9, while 3.12 still gives 168 passed. Note: `uv run --python 3.9` in the project dir was NOT used, because it would rebuild the project `.venv`; a scratch 3.9 venv was used instead. |

## Integrity of the project tree

- Temporary mutations were made only to `src/test_tamper_guard/rules.py`, `cli.py` and `diffparse.py`;
  each was restored from a scratch copy and checked with `sha256sum -c` (OK for all three; see c6-mut, c9-mut, c11-mut logs).
  Original checksums: rules.py `c72d36fa...7dec`, cli.py `ec7a22c0...3431`, diffparse.py `add3ca99...a25b`.
- After all probes: 413 non-cache project files (excluding `.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache`) all match the checksums taken before C13 (`ALL_413_FILES_MATCH`, tree.log). Files' mtimes changed for the three restored files.
- `__pycache__` directories under `src/test_tamper_guard/` were deleted (regenerable cache) to prevent stale bytecode in mutation runs.
- The only file added to the project is this one.

## Verbatim probe records

### C1 — pytest.approx

```
$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c1) ../.venv/bin/python -m pytest -q -p no:cacheprovider test_c1.py -rA 2>&1 | tail -9
==================================== PASSES ====================================
=========================== short test summary info ============================
PASSED test_c1.py::test_rel_loose
PASSED test_c1.py::test_abs_loose
PASSED test_c1.py::test_rel_abs_kw
FAILED test_c1.py::test_base - assert 1.001 == 1.0 ± 1.0e-06
FAILED test_c1.py::test_rel_tight - assert 1.001 == 1.0 ± 1.0e-04
FAILED test_c1.py::test_abs_tight - assert 1.001 == 1.0 ± 1.0e-04
3 failed, 3 passed in 0.04s
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c1) ../.venv/bin/python -m pytest -q -p no:cacheprovider test_c1.py::test_rel_loose test_c1.py::test_abs_loose test_c1.py::test_rel_abs_kw
...                                                                      [100%]
3 passed in 0.01s
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c1) ../.venv/bin/python -m pytest -q -p no:cacheprovider test_c1.py::test_rel_tight
F                                                                        [100%]
=================================== FAILURES ===================================
________________________________ test_rel_tight ________________________________

>   def test_rel_tight(): assert 1.001 == pytest.approx(1.0, rel=1e-4)       # FAIL
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   assert 1.001 == 1.0 ± 1.0e-04
E     
E     comparison failed
E     Obtained: 1.001
E     Expected: 1.0 ± 1.0e-04

test_c1.py:3: AssertionError
=========================== short test summary info ============================
FAILED test_c1.py::test_rel_tight - assert 1.001 == 1.0 ± 1.0e-04
1 failed in 0.03s
rc=1

```

Probe file c1/test_c1.py:
```python
import pytest
def test_base():      assert 1.001 == pytest.approx(1.0)                 # default rel=1e-6 -> FAIL
def test_rel_tight(): assert 1.001 == pytest.approx(1.0, rel=1e-4)       # FAIL
def test_rel_loose(): assert 1.001 == pytest.approx(1.0, rel=1e-2)       # PASS
def test_abs_tight(): assert 1.001 == pytest.approx(1.0, abs=1e-4)       # FAIL
def test_abs_loose(): assert 1.001 == pytest.approx(1.0, abs=1e-2)       # PASS
def test_rel_abs_kw(): assert 1.001 == pytest.approx(1.0, rel=1e-9, abs=1e-2)  # both accepted, PASS
```

### C2 — pytest skip/xfail markers

```
$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c2) cat test_none.py; ../.venv/bin/python -m pytest -q -p no:cacheprovider test_none.py 2>&1 | tail -1; exit ${PIPESTATUS[0]}
import pytest

def test_x():
    assert 1 == 2
1 failed in 0.02s
rc=1

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c2) cat test_mark_skip.py; ../.venv/bin/python -m pytest -q -p no:cacheprovider test_mark_skip.py 2>&1 | tail -1; exit ${PIPESTATUS[0]}
import pytest
@pytest.mark.skip(reason='r')
def test_x():
    assert 1 == 2
1 skipped in 0.00s
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c2) cat test_mark_skipif.py; ../.venv/bin/python -m pytest -q -p no:cacheprovider test_mark_skipif.py 2>&1 | tail -1; exit ${PIPESTATUS[0]}
import pytest
@pytest.mark.skipif(True, reason='r')
def test_x():
    assert 1 == 2
1 skipped in 0.01s
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c2) cat test_mark_xfail.py; ../.venv/bin/python -m pytest -q -p no:cacheprovider test_mark_xfail.py 2>&1 | tail -1; exit ${PIPESTATUS[0]}
import pytest
@pytest.mark.xfail
def test_x():
    assert 1 == 2
1 xfailed in 0.02s
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c2) cat test_call_skip.py; ../.venv/bin/python -m pytest -q -p no:cacheprovider test_call_skip.py 2>&1 | tail -1; exit ${PIPESTATUS[0]}
import pytest

def test_x():
    pytest.skip('r'); assert 1 == 2
1 skipped in 0.01s
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c2) cat test_call_xfail.py; ../.venv/bin/python -m pytest -q -p no:cacheprovider test_call_xfail.py 2>&1 | tail -1; exit ${PIPESTATUS[0]}
import pytest

def test_x():
    pytest.xfail('r'); assert 1 == 2
1 xfailed in 0.02s
rc=0

```

### C3 — unittest assertAlmostEqual and skip decorators

```
$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c3) ../.venv/bin/python -m unittest -v t_c3 2>&1 | grep -E 'sig:|\.\.\.|^Ran|FAILED|^OK'; exit ${PIPESTATUS[0]}
test_delta_big (t_c3.T.test_delta_big) ... ok
test_delta_small (t_c3.T.test_delta_small) ... FAIL
test_msg_kw (t_c3.T.test_msg_kw) ... ok
test_places2 (t_c3.T.test_places2) ... ok
test_places4 (t_c3.T.test_places4) ... FAIL
test_places7_default (t_c3.T.test_places7_default) ... FAIL
Ran 6 tests in 0.002s
FAILED (failures=3)
sig: (self, first, second, places=None, msg=None, delta=None)
rc=1

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c3) sed -n 3p u_none.py; ../.venv/bin/python -m unittest u_none 2>&1 | tail -1; exit ${PIPESTATUS[0]}
    
FAILED (failures=1)
rc=1

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c3) sed -n 3p u_skip.py; ../.venv/bin/python -m unittest u_skip 2>&1 | tail -1; exit ${PIPESTATUS[0]}
    @unittest.skip('r')
OK (skipped=1)
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c3) sed -n 3p u_skipIf.py; ../.venv/bin/python -m unittest u_skipIf 2>&1 | tail -1; exit ${PIPESTATUS[0]}
    @unittest.skipIf(True,'r')
OK (skipped=1)
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c3) sed -n 3p u_skipUnless.py; ../.venv/bin/python -m unittest u_skipUnless 2>&1 | tail -1; exit ${PIPESTATUS[0]}
    @unittest.skipUnless(False,'r')
OK (skipped=1)
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c3) sed -n 3p u_expectedFailure.py; ../.venv/bin/python -m unittest u_expectedFailure 2>&1 | tail -1; exit ${PIPESTATUS[0]}
    @unittest.expectedFailure
OK (expected failures=1)
rc=0

```

Probe file c3/t_c3.py:
```python
import unittest, inspect, sys
print("sig:", inspect.signature(unittest.TestCase.assertAlmostEqual))
class T(unittest.TestCase):
    # 1.0 vs 1.001: diff 0.001
    def test_places7_default(self): self.assertAlmostEqual(1.0, 1.001)            # FAIL
    def test_places4(self):         self.assertAlmostEqual(1.0, 1.001, places=4)  # FAIL
    def test_places2(self):         self.assertAlmostEqual(1.0, 1.001, places=2)  # PASS (fewer places looser)
    def test_delta_small(self):     self.assertAlmostEqual(1.0, 1.001, delta=1e-4)# FAIL
    def test_delta_big(self):       self.assertAlmostEqual(1.0, 1.001, delta=1e-2)# PASS
    def test_msg_kw(self):          self.assertAlmostEqual(1.0, 1.0, places=None, msg="m", delta=None)
```

### C4 — numpy / torch tolerances (warnings promoted to errors)

```
$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c4) ../.venv/bin/python -W error::DeprecationWarning -W error::FutureWarning -W error::UserWarning p_c4.py
numpy sig: (actual, desired, rtol=1e-07, atol=0, equal_nan=True, err_msg='', verbose=True, *, strict=False)
torch sig: (actual: Any, expected: Any, *, allow_subclasses: bool = True, rtol: float | None = None, atol: float | None = None, equal_nan: bool = False, check_device: bool = True, check_dtype: bool = True, check_layout: bool = True, check_stride: bool = False, msg: str | collections.abc.Callable[[str], str] | None = None)
np default         FAIL
np rtol=1e-4       FAIL
np rtol=1e-2       PASS
np rtol=0 atol=1e-4 FAIL
np rtol=0 atol=1e-2 PASS
torch default      FAIL
torch r1e-4 a0     FAIL
torch r1e-2 a0     PASS
torch r0 a1e-4     FAIL
torch r0 a1e-2     PASS
torch rtol only   : ValueError: Both 'rtol' and 'atol' must be either specified or omitted, but got no atol.
rc=0

```

```python
import inspect, numpy as np, torch
print("numpy sig:", inspect.signature(np.testing.assert_allclose))
print("torch sig:", inspect.signature(torch.testing.assert_close))
def ok(f):
    try: f(); return "PASS"
    except AssertionError: return "FAIL"
a, d = np.array([1.001]), np.array([1.0])
print("np default        ", ok(lambda: np.testing.assert_allclose(a, d)))
print("np rtol=1e-4      ", ok(lambda: np.testing.assert_allclose(a, d, rtol=1e-4)))
print("np rtol=1e-2      ", ok(lambda: np.testing.assert_allclose(a, d, rtol=1e-2)))
print("np rtol=0 atol=1e-4", ok(lambda: np.testing.assert_allclose(a, d, rtol=0, atol=1e-4)))
print("np rtol=0 atol=1e-2", ok(lambda: np.testing.assert_allclose(a, d, rtol=0, atol=1e-2)))
ta, te = torch.tensor([1.001], dtype=torch.float64), torch.tensor([1.0], dtype=torch.float64)
print("torch default     ", ok(lambda: torch.testing.assert_close(ta, te)))
print("torch r1e-4 a0    ", ok(lambda: torch.testing.assert_close(ta, te, rtol=1e-4, atol=0)))
print("torch r1e-2 a0    ", ok(lambda: torch.testing.assert_close(ta, te, rtol=1e-2, atol=0)))
print("torch r0 a1e-4    ", ok(lambda: torch.testing.assert_close(ta, te, rtol=0, atol=1e-4)))
print("torch r0 a1e-2    ", ok(lambda: torch.testing.assert_close(ta, te, rtol=0, atol=1e-2)))
try: torch.testing.assert_close(ta, te, rtol=1e-2); print("torch rtol only   : no error")
except ValueError as e: print("torch rtol only   : ValueError:", e)
```

### C5 — jest toBeCloseTo

```
$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c5/c5.test.js --verbose 2>&1 | grep -E '(✓|✕|√|×|Tests:)' ; npx jest --ci c5/c5.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{for(const t of JSON.parse(s).testResults[0].assertionResults)console.log(t.status.padEnd(7),t.title)})'
Tests:       3 failed, 3 passed, 6 total
passed  default numDigits=2
failed  numDigits=4
failed  numDigits=3
passed  numDigits=2
failed  default fails where 3 fails: 1.01
passed  same 1.01 with numDigits=1
rc=0

```

```js
// |1.0 - 1.001| = 0.001
test('default numDigits=2', () => { expect(1.001).toBeCloseTo(1.0); });     // PASS (0.001 < 0.005)
test('numDigits=4',  () => { expect(1.001).toBeCloseTo(1.0, 4); });         // FAIL
test('numDigits=3',  () => { expect(1.001).toBeCloseTo(1.0, 3); });         // FAIL? 0.001 < 0.0005 false -> FAIL
test('numDigits=2',  () => { expect(1.001).toBeCloseTo(1.0, 2); });         // PASS
test('default fails where 3 fails: 1.01', () => { expect(1.01).toBeCloseTo(1.0); });   // FAIL (0.01 > 0.005)
test('same 1.01 with numDigits=1', () => { expect(1.01).toBeCloseTo(1.0, 1); });       // PASS
```

### C6 — jest markers (runtime)

```
$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c6/base.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const r=JSON.parse(s);console.log("base", "success="+r.success, r.testResults[0].assertionResults.map(t=>t.title+":"+t.status).join(" "))})'; exit ${PIPESTATUS[0]}
base success=false t:failed
rc=1

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c6/it_skip.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const r=JSON.parse(s);console.log("it_skip", "success="+r.success, r.testResults[0].assertionResults.map(t=>t.title+":"+t.status).join(" "))})'; exit ${PIPESTATUS[0]}
it_skip success=true t:pending
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c6/test_skip.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const r=JSON.parse(s);console.log("test_skip", "success="+r.success, r.testResults[0].assertionResults.map(t=>t.title+":"+t.status).join(" "))})'; exit ${PIPESTATUS[0]}
test_skip success=true t:pending
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c6/describe_skip.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const r=JSON.parse(s);console.log("describe_skip", "success="+r.success, r.testResults[0].assertionResults.map(t=>t.title+":"+t.status).join(" "))})'; exit ${PIPESTATUS[0]}
describe_skip success=true t:pending
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c6/xit.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const r=JSON.parse(s);console.log("xit", "success="+r.success, r.testResults[0].assertionResults.map(t=>t.title+":"+t.status).join(" "))})'; exit ${PIPESTATUS[0]}
xit success=true t:pending
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c6/xtest.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const r=JSON.parse(s);console.log("xtest", "success="+r.success, r.testResults[0].assertionResults.map(t=>t.title+":"+t.status).join(" "))})'; exit ${PIPESTATUS[0]}
xtest success=true t:pending
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c6/xdescribe.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const r=JSON.parse(s);console.log("xdescribe", "success="+r.success, r.testResults[0].assertionResults.map(t=>t.title+":"+t.status).join(" "))})'; exit ${PIPESTATUS[0]}
xdescribe success=true t:pending
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c6/test_todo.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const r=JSON.parse(s);console.log("test_todo", "success="+r.success, r.testResults[0].assertionResults.map(t=>t.title+":"+t.status).join(" "))})'; exit ${PIPESTATUS[0]}
test_todo success=true t:todo
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c6/test_failing.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const r=JSON.parse(s);console.log("test_failing", "success="+r.success, r.testResults[0].assertionResults.map(t=>t.title+":"+t.status).join(" "))})'; exit ${PIPESTATUS[0]}
test_failing success=true t:passed
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c6/focus_base.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const r=JSON.parse(s);console.log("focus_base", "success="+r.success, r.testResults[0].assertionResults.map(t=>t.title+":"+t.status).join(" "))})'; exit ${PIPESTATUS[0]}
focus_base success=false a:passed sib:failed
rc=1

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c6/it_only.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const r=JSON.parse(s);console.log("it_only", "success="+r.success, r.testResults[0].assertionResults.map(t=>t.title+":"+t.status).join(" "))})'; exit ${PIPESTATUS[0]}
it_only success=true a:passed sib:pending
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c6/test_only.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const r=JSON.parse(s);console.log("test_only", "success="+r.success, r.testResults[0].assertionResults.map(t=>t.title+":"+t.status).join(" "))})'; exit ${PIPESTATUS[0]}
test_only success=true a:passed sib:pending
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c6/fit.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const r=JSON.parse(s);console.log("fit", "success="+r.success, r.testResults[0].assertionResults.map(t=>t.title+":"+t.status).join(" "))})'; exit ${PIPESTATUS[0]}
fit success=true a:passed sib:pending
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c6/fdescribe.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const r=JSON.parse(s);console.log("fdescribe", "success="+r.success, r.testResults[0].assertionResults.map(t=>t.title+":"+t.status).join(" "))})'; exit ${PIPESTATUS[0]}
fdescribe success=true a:passed sib:pending
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js) npx jest --ci c6/describe_only.test.js --json 2>/dev/null | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const r=JSON.parse(s);console.log("describe_only", "success="+r.success, r.testResults[0].assertionResults.map(t=>t.title+":"+t.status).join(" "))})'; exit ${PIPESTATUS[0]}
describe_only success=true a:passed sib:pending
rc=0

```

Jest probe files (each run separately):
```js
// base.test.js
test('t', () => { expect(1).toBe(2); });
// describe_only.test.js
describe.only('d', () => { test('a', () => { expect(1).toBe(1); }); });
test('sib', () => { expect(1).toBe(2); });
// describe_skip.test.js
describe.skip('d', () => { test('t', () => { expect(1).toBe(2); }); });
// fdescribe.test.js
fdescribe('d', () => { test('a', () => { expect(1).toBe(1); }); });
test('sib', () => { expect(1).toBe(2); });
// fit.test.js
fit('a', () => { expect(1).toBe(1); });
test('sib', () => { expect(1).toBe(2); });
// focus_base.test.js
test('a', () => { expect(1).toBe(1); });
test('sib', () => { expect(1).toBe(2); });
// it_only.test.js
it.only('a', () => { expect(1).toBe(1); });
test('sib', () => { expect(1).toBe(2); });
// it_skip.test.js
it.skip('t', () => { expect(1).toBe(2); });
// test_failing.test.js
test.failing('t', () => { expect(1).toBe(2); });
// test_only.test.js
test.only('a', () => { expect(1).toBe(1); });
test('sib', () => { expect(1).toBe(2); });
// test_skip.test.js
test.skip('t', () => { expect(1).toBe(2); });
// test_todo.test.js
test.todo('t');
// xdescribe.test.js
xdescribe('d', () => { test('t', () => { expect(1).toBe(2); }); });
// xit.test.js
xit('t', () => { expect(1).toBe(2); });
// xtest.test.js
xtest('t', () => { expect(1).toBe(2); });
```

### C6 — engine on real git diffs + control

```
$ (cwd=/home/rajib2k5/dev/test-tamper-guard) /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c6_engine.sh
it.skip        engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
test.skip      engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
describe.skip  engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
xit            engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
xtest          engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
xdescribe      engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
test.todo      engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
test.failing   engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
it.only        engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
test.only      engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
fit            engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
fdescribe      engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
describe.only  engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c6repo) cd /home/rajib2k5/dev/test-tamper-guard && PYTHONPATH=src python3 -B -m test_tamper_guard --diff /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c6repo/patches/control-rename-title.patch --format json
{
  "version": "0.1.0",
  "findings": [],
  "counts": {
    "high": 0,
    "medium": 0,
    "low": 0
  }
}
rc=0

```

### C6 — falsifier (remove "only" from JS_MARKERS) and restore

```
$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c6repo) sha256sum /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/rules.py | tee /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/rules.sha.before; grep -n 'JS_MARKERS = ' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/rules.py
c72d36fa195beb446bafb19b7880b5bc96bead5edbacabc0d00d80328d157dec  /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/rules.py
279:JS_MARKERS = ("skip", "only", "todo", "failing", "skipIf")
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c6repo) sed -i 's/JS_MARKERS = ("skip", "only", "todo", "failing", "skipIf")/JS_MARKERS = ("skip", "todo", "failing", "skipIf")/' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/rules.py && grep -n 'JS_MARKERS = ' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/rules.py && find /home/rajib2k5/dev/test-tamper-guard/src -name __pycache__ -exec rm -rf {} + ; /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c6_engine.sh
279:JS_MARKERS = ("skip", "todo", "failing", "skipIf")
it.skip        engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
test.skip      engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
describe.skip  engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
xit            engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
xtest          engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
xdescribe      engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
test.todo      engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
test.failing   engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
it.only        engine_rc=0 check_rc=1 MISS []
test.only      engine_rc=0 check_rc=1 MISS []
fit            engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
fdescribe      engine_rc=1 check_rc=0 OK [('skip-added', 'high')]
describe.only  engine_rc=0 check_rc=1 MISS []
rc=1

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c6repo) sha256sum /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/rules.py; sha256sum -c /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/rules.sha.before; find /home/rajib2k5/dev/test-tamper-guard/src -name __pycache__ -exec rm -rf {} + ; /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c6_engine.sh >/dev/null; echo engine_after_restore_rc=$?
shell-init: error retrieving current directory: getcwd: cannot access parent directories: No such file or directory
c72d36fa195beb446bafb19b7880b5bc96bead5edbacabc0d00d80328d157dec  /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/rules.py
/home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/rules.py: OK
shell-init: error retrieving current directory: getcwd: cannot access parent directories: No such file or directory
chdir: error retrieving current directory: getcwd: cannot access parent directories: No such file or directory
engine_after_restore_rc=0
rc=0

```

<details><summary>c6_engine.sh</summary>

```
#!/bin/bash
# For each jest marker: real git repo, commit base test, rewrite with marker, git diff -> engine JSON.
W=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b
P=/home/rajib2k5/dev/test-tamper-guard
R=$W/c6repo; rm -rf $R; mkdir -p $R/patches; cd $R; git init -q; git config user.email p@x; git config user.name p
BASE="describe('suite', () => {
  test('adds', () => {
    expect(add(1, 2)).toBe(3);
  });
});"
printf '%s\n' "$BASE" > math.test.js; git add .; git commit -qm base
declare -A NEW
NEW[it.skip]="describe('suite', () => {
  it.skip('adds', () => {
    expect(add(1, 2)).toBe(3);
  });
});"
for m in test.skip xit xtest test.failing it.only test.only fit; do
NEW[$m]="describe('suite', () => {
  $m('adds', () => {
    expect(add(1, 2)).toBe(3);
  });
});"; done
for m in describe.skip xdescribe fdescribe describe.only; do
NEW[$m]="$m('suite', () => {
  test('adds', () => {
    expect(add(1, 2)).toBe(3);
  });
});"; done
NEW[test.todo]="describe('suite', () => {
  test.todo('adds');
});"
fail=0
for m in it.skip test.skip describe.skip xit xtest xdescribe test.todo test.failing it.only test.only fit fdescribe describe.only; do
  git checkout -q -- math.test.js
  printf '%s\n' "${NEW[$m]}" > math.test.js
  git diff > patches/$m.patch
  out=$(cd $P && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -B -m test_tamper_guard --diff $R/patches/$m.patch --format json); erc=$?
  verdict=$(printf '%s' "$out" | python3 -c '
import json,sys
d=json.load(sys.stdin); r={"high":3,"medium":2,"low":1}
hits=[(f["rule"],f["severity"]) for f in d["findings"] if f["rule"]=="skip-added"]
ok=any(r[s]>=2 for _,s in hits)
print(("OK " if ok else "MISS ")+repr([(f["rule"],f["severity"]) for f in d["findings"]]))
sys.exit(0 if ok else 1)'); vrc=$?
  [ $vrc -ne 0 ] && fail=1
  printf '%-14s engine_rc=%d check_rc=%d %s\n' "$m" $erc $vrc "$verdict"
done
git checkout -q -- math.test.js
exit $fail
```
</details>

### C7/C8 — claude CLI version, SDK type definitions, binary strings

```
$ (cwd=/tmp) which claude; claude --version
/home/rajib2k5/.local/bin/claude
2.1.296 (Claude Code)
rc=0

$ (cwd=/tmp) timeout 120 find ~ /usr/lib/node_modules /usr/local/lib -path '*claude-agent-sdk*' \( -name '*.d.ts' -o -name 'types.py' \) 2>/dev/null | grep -v '/egv-b/' | head -20
/home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/browser-sdk.d.ts
/home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/bridge.d.ts
/home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/sdk.d.ts
/home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/sdk-tools.d.ts
/home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/agentSdkTypes.d.ts
/home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/extractFromBunfs.d.ts
rc=0

$ (cwd=/home/rajib2k5/dev/test-tamper-guard) node -e 'console.log(require("/home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/package.json").version)'; grep -n 'PreToolUseHookInput\b\|type BaseHookInput\|PreToolUseHookSpecificOutput' /home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/sdk.d.ts | head
0.3.195
156:export declare type BaseHookInput = {
347:        PreToolUseHookInput,
348:        PreToolUseHookSpecificOutput,
777:export declare type HookInput = PreToolUseHookInput | PostToolUseHookInput | PostToolUseFailureHookInput | PostToolBatchHookInput | PermissionDeniedHookInput | NotificationHookInput | UserPromptSubmitHookInput | UserPromptExpansionHookInput | SessionStartHookInput | SessionEndHookInput | StopHookInput | StopFailureHookInput | SubagentStartHookInput | SubagentStopHookInput | PreCompactHookInput | PostCompactHookInput | PermissionRequestHookInput | SetupHookInput | TeammateIdleHookInput | TaskCreatedHookInput | TaskCompletedHookInput | ElicitationHookInput | ElicitationResultHookInput | ConfigChangeHookInput | InstructionsLoadedHookInput | WorktreeCreateHookInput | WorktreeRemoveHookInput | CwdChangedHookInput | FileChangedHookInput | MessageDisplayHookInput;
2164:export declare type PreToolUseHookInput = BaseHookInput & {
2171:export declare type PreToolUseHookSpecificOutput = {
6418:    hookSpecificOutput?: PreToolUseHookSpecificOutput | UserPromptSubmitHookSpecificOutput | UserPromptExpansionHookSpecificOutput | SessionStartHookSpecificOutput | SetupHookSpecificOutput | SubagentStartHookSpecificOutput | PostToolUseHookSpecificOutput | PostToolUseFailureHookSpecificOutput | PostToolBatchHookSpecificOutput | StopHookSpecificOutput | SubagentStopHookSpecificOutput | PermissionDeniedHookSpecificOutput | NotificationHookSpecificOutput | PermissionRequestHookSpecificOutput | ElicitationHookSpecificOutput | ElicitationResultHookSpecificOutput | CwdChangedHookSpecificOutput | FileChangedHookSpecificOutput | WorktreeCreateHookSpecificOutput | MessageDisplayHookSpecificOutput;
rc=0

$ (cwd=/home/rajib2k5/dev/test-tamper-guard) sed -n 156,175p /home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/sdk.d.ts; sed -n 2164,2185p /home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/sdk.d.ts; grep -n 'interface FileWriteInput\|interface FileEditInput\|MultiEdit' /home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/sdk-tools.d.ts | head
export declare type BaseHookInput = {
    session_id: string;
    transcript_path: string;
    cwd: string;
    permission_mode?: string;
    /**
     * Subagent identifier. Present only when the hook fires from within a subagent (e.g., a tool called by an AgentTool worker). Absent for the main thread, even in --agent sessions. Use this field (not agent_type) to distinguish subagent calls from main-thread calls.
     */
    agent_id?: string;
    /**
     * Agent type name (e.g., "general-purpose", "code-reviewer"). Present when the hook fires from within a subagent (alongside agent_id), or on the main thread of a session started with --agent (without agent_id).
     */
    agent_type?: string;
    /**
     * Reasoning effort applied to the current turn. Same shape as StatusLineCommandInput.effort. Present for hooks that fire within a tool-use context (PreToolUse, PostToolUse, Stop, SubagentStop, etc.) on a model that supports the effort parameter; absent for session-lifecycle hooks and models without effort support.
     */
    effort?: {
        /**
         * Active effort level for the current turn (e.g., "low", "medium", "high", "xhigh", "max"), after any silent downgrade for the selected model. Also exposed to hook commands and Bash as the CLAUDE_EFFORT env var.
         */
export declare type PreToolUseHookInput = BaseHookInput & {
    hook_event_name: 'PreToolUse';
    tool_name: string;
    tool_input: unknown;
    tool_use_id: string;
};

export declare type PreToolUseHookSpecificOutput = {
    hookEventName: 'PreToolUse';
    permissionDecision?: HookPermissionDecision;
    permissionDecisionReason?: string;
    updatedInput?: Record<string, unknown>;
    additionalContext?: string;
};

/**
 * Per-key provenance entry.
 * @alpha
 */
export declare type ProvenanceEntry = {
    source: ResolvedSettingSource;
    /** Absolute path to the settings file, for filesystem-backed sources. */
511:export interface FileEditInput {
547:export interface FileWriteInput {
rc=0

$ (cwd=/home/rajib2k5/dev/test-tamper-guard) sed -n 511,560p /home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/sdk-tools.d.ts | grep -v '^\s*\*\|/\*\*'; grep -n 'type HookPermissionDecision' /home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/sdk.d.ts; grep -n 'HookPermissionDecision =' /home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/sdk.d.ts | head -2; grep -c -i 'multiedit' /home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/sdk-tools.d.ts /home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/sdk.d.ts
export interface FileEditInput {
  file_path: string;
  old_string: string;
  new_string: string;
  replace_all?: boolean;
}
export interface FileReadInput {
  file_path: string;
  offset?: number;
  limit?: number;
  pages?: string;
}
export interface FileWriteInput {
  file_path: string;
  content: string;
}
export interface GlobInput {
781:export declare type HookPermissionDecision = 'allow' | 'deny' | 'ask' | 'defer';
781:export declare type HookPermissionDecision = 'allow' | 'deny' | 'ask' | 'defer';
/home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/sdk-tools.d.ts:0
/home/rajib2k5/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk/sdk.d.ts:0
rc=1

$ (cwd=/home/rajib2k5/dev/test-tamper-guard) ls -la /home/rajib2k5/.local/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe | awk '{print $5, $9}'; for s in permissionDecisionReason hookSpecificOutput MultiEdit CLAUDE_PLUGIN_ROOT; do printf '%s: ' $s; grep -a -o $s /home/rajib2k5/.local/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe | wc -l; done
256434168 /home/rajib2k5/.local/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe
permissionDecisionReason: 48
hookSpecificOutput: 187
MultiEdit: 10
CLAUDE_PLUGIN_ROOT: 62
rc=0

```

### C9 — github format escaping

```
$ (cwd=/home/rajib2k5/dev/test-tamper-guard) /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c9_probe.sh
github_rc=1
json_rc=1
--- raw github output (od -c):
0000000   :   :   e   r   r   o   r       f   i   l   e   =   t   e   s
0000020   t   s   /   a   %   2   C   b   %   3   A   c   /   t   e   s
0000040   t   _   p   c   t   .   p   y   ,   l   i   n   e   =   2   ,
0000060   t   i   t   l   e   =   t   e   s   t   -   t   a   m   p   e
0000100   r   -   g   u   a   r   d       s   k   i   p   -   a   d   d
0000120   e   d       (   h   i   g   h   )   :   :   a   d   d   e   d
0000140       s   k   i   p       m   a   r   k   e   r       p   y   t
0000160   e   s   t   .   m   a   r   k   .   s   k   i   p       w   i
0000200   t   h   o   u   t       a       l   i   n   k   e   d       i
0000220   s   s   u   e   %   0   A   @   p   y   t   e   s   t   .   m
0000240   a   r   k   .   s   k   i   p   (   r   e   a   s   o   n   =
0000260   "   f   l   a   k   y       1   0   0   %   2   5       o   f
0000300       t   h   e       t   i   m   e   "   )  \n
0000314
findings: [('skip-added', 'high', 'tests/a,b:c/test_pct.py', 2)]
raw message+evidence: ['added skip marker pytest.mark.skip without a linked issue\n@pytest.mark.skip(reason="flaky 100% of the time")']
expected: b'::error file=tests/a%2Cb%3Ac/test_pct.py,line=2,title=test-tamper-guard skip-added (high)::added skip marker pytest.mark.skip without a linked issue%0A@pytest.mark.skip(reason="flaky 100%25 of the time")\n'
got     : b'::error file=tests/a%2Cb%3Ac/test_pct.py,line=2,title=test-tamper-guard skip-added (high)::added skip marker pytest.mark.skip without a linked issue%0A@pytest.mark.skip(reason="flaky 100%25 of the time")\n'
CHECK PASS byte-identical to claim-derived escaping
CHECK PASS path escaped a%2Cb%3Ac
CHECK PASS message has %25 for literal %
CHECK PASS message has %0A for newline
CHECK PASS one physical line per finding
CHECK PASS no raw % that is not an escape
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c9cr) cd /home/rajib2k5/dev/test-tamper-guard && PYTHONPATH=src python3 -B -m test_tamper_guard --diff /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c9cr.patch --format github | od -c | grep -n '\\r' ; cd /home/rajib2k5/dev/test-tamper-guard && PYTHONPATH=src python3 -B -m test_tamper_guard --diff /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c9cr.patch --format github
::error file=test_cr.py,line=2,title=test-tamper-guard skip-added (high)::added skip marker pytest.mark.skip without a linked issue%0A@pytest.mark.skip(reason="x")
rc=1

$ (cwd=/home/rajib2k5/dev/test-tamper-guard) cd /home/rajib2k5/dev/test-tamper-guard && PYTHONPATH=src python3 -B -c 'from test_tamper_guard.cli import escape_data as d, escape_property as p; import sys; r=[d("a%b\rc\nd")=="a%25b%0Dc%0Ad", p("x:y,z%\r\n")=="x%3Ay%2Cz%25%0D%0A", d("%0A")=="%250A"]; print(r); sys.exit(0 if all(r) else 1)'
[True, True, True]
rc=0

```

### C9 — falsifier (drop ',' escape) and restore

```
$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sha256sum /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/cli.py | tee /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/cli.sha.before; grep -n 'replace(",", "%2C")' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/cli.py
ec7a22c06f93c0a027e5e05128f32665b5161c6c46dbdbef2fd2596b32723431  /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/cli.py
31:    return escape_data(s).replace(":", "%3A").replace(",", "%2C")
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sed -i 's/.replace(",", "%2C")//' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/cli.py; grep -n 'def escape_property' -A3 /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/cli.py; rm -rf /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/__pycache__; /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c9_probe.sh 2>&1 | grep -E 'got|CHECK'; exit ${PIPESTATUS[0]}
29:def escape_property(s: str) -> str:
30-    """GitHub workflow-command property escaping."""
31-    return escape_data(s).replace(":", "%3A")
32-
got     : b'::error file=tests/a,b%3Ac/test_pct.py,line=2,title=test-tamper-guard skip-added (high)::added skip marker pytest.mark.skip without a linked issue%0A@pytest.mark.skip(reason="flaky 100%25 of the time")\n'
CHECK FAIL byte-identical to claim-derived escaping
CHECK FAIL path escaped a%2Cb%3Ac
CHECK PASS message has %25 for literal %
CHECK PASS message has %0A for newline
CHECK PASS one physical line per finding
CHECK PASS no raw % that is not an escape
rc=1

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sha256sum -c /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/cli.sha.before && /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c9_probe.sh >/dev/null; echo probe_after_restore_rc=$?
/home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/cli.py: OK
probe_after_restore_rc=0
rc=0

```

<details><summary>c9_probe.sh</summary>

```
#!/bin/bash
W=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b
P=/home/rajib2k5/dev/test-tamper-guard
R=$W/c9repo; rm -rf $R; mkdir -p "$R/tests/a,b:c"; cd $R; git init -q; git config user.email p@x; git config user.name p
f="tests/a,b:c/test_pct.py"
printf 'def test_rate():\n    assert rate() == 1\n' > "$f"; git add -A; git commit -qm base
printf 'import pytest\n@pytest.mark.skip(reason="flaky 100%% of the time")\ndef test_rate():\n    assert rate() == 1\n' > "$f"
git diff > $W/c9.patch
cd $P
PYTHONPATH=src python3 -B -m test_tamper_guard --diff $W/c9.patch --format github > $W/c9.github.out; echo "github_rc=$?"
PYTHONPATH=src python3 -B -m test_tamper_guard --diff $W/c9.patch --format json > $W/c9.json.out; echo "json_rc=$?"
echo "--- raw github output (od -c):"; od -c $W/c9.github.out | head -40
python3 - "$W" <<'PY'
import json, sys
W = sys.argv[1]
# Escaping derived from the CLAIM text, not from the code:
def data(s):  return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
def prop(s):  return data(s).replace(":", "%3A").replace(",", "%2C")
got = open(W + "/c9.github.out", "rb").read()
fs = json.load(open(W + "/c9.json.out"))["findings"]
exp = b""
for f in fs:
    cmd = "error" if f["severity"] == "high" else "warning"
    title = "test-tamper-guard %s (%s)" % (f["rule"], f["severity"])
    exp += ("::%s file=%s,line=%d,title=%s::%s\n" % (cmd, prop(f["path"]), f["line"], prop(title),
            data(f["message"] + "\n" + f["evidence"]))).encode()
print("findings:", [(f["rule"], f["severity"], f["path"], f["line"]) for f in fs])
print("raw message+evidence:", repr([f["message"] + "\n" + f["evidence"] for f in fs]))
print("expected:", exp)
print("got     :", got)
line = got.split(b"\n")[0]
checks = {
  "byte-identical to claim-derived escaping": got == exp,
  "path escaped a%2Cb%3Ac": b"file=tests/a%2Cb%3Ac/test_pct.py," in got,
  "message has %25 for literal %": b"100%25" in got,
  "message has %0A for newline": b"%0A" in line,
  "one physical line per finding": got.count(b"\n") == len(fs),
  "no raw % that is not an escape": all(line[i+1:i+3] in (b"25", b"0A", b"0D", b"3A", b"2C") for i in range(len(line)) if line[i:i+1] == b"%"),
}
for k, v in checks.items(): print("CHECK", "PASS" if v else "FAIL", k)
sys.exit(0 if all(checks.values()) and fs else 1)
PY
```
</details>

### C10 — act/docker availability; shallow vs full clone

```
$ (cwd=/home/rajib2k5/dev/test-tamper-guard) which act; gh extension list 2>&1 | grep -i act; docker --version 2>&1
Docker version 29.6.2, build dfc4efb
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c10/origin) cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c10/origin; BASE=$(git rev-parse HEAD~1); HEAD=$(git rev-parse HEAD); git clone -q --depth=1 file:///tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c10/origin /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c10/shallow; cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c10/shallow; echo shallow:; git diff --stat $BASE $HEAD; echo diff_rc=$?; git clone -q file:///tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c10/origin /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c10/full; cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c10/full; echo full:; git diff --stat $BASE $HEAD; echo diff_rc=$?
shallow:
fatal: bad object 2e66d4c8aa9d98c84d91bd84376807d312ac93d6
diff_rc=128
full:
 f | 1 +
 1 file changed, 1 insertion(+)
diff_rc=0
rc=0

$ (cwd=/home/rajib2k5/dev/test-tamper-guard) cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c10/origin; BASE=$(git rev-parse HEAD~1); HEAD=$(git rev-parse HEAD); cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c10/shallow && PYTHONPATH=/home/rajib2k5/dev/test-tamper-guard/src python3 -B -m test_tamper_guard --range $BASE..$HEAD --format github; echo shallow_cli_rc=$?; cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c10/full && PYTHONPATH=/home/rajib2k5/dev/test-tamper-guard/src python3 -B -m test_tamper_guard --range $BASE..$HEAD --format github; echo full_cli_rc=$?
test-tamper-guard: git diff failed: fatal: bad object 2e66d4c8aa9d98c84d91bd84376807d312ac93d6
shallow_cli_rc=2
full_cli_rc=0
rc=0

```

### C11 — diff headers from real repos

```
$ (cwd=/home/rajib2k5/dev/test-tamper-guard) /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c11_probe.sh
=== rename: header lines
diff --git a/test_old.py b/test_new.py
similarity index 82%
rename from test_old.py
rename to test_new.py
--- a/test_old.py
+++ b/test_new.py
CLI rc=0 findings= [('expected-changed', 'medium', 'test_new.py', 10)]
parse: [('test_old.py', 'test_new.py', False, False, True, False, [('-', '    assert f(3) == 4', 10, None), ('+', '    assert f(3) == 5', None, 10)])]
CHECK PASS rename expected ('test_old.py', 'test_new.py', False, False, True, False)
=== rename100: header lines
diff --git a/test_a.py b/test_b.py
similarity index 100%
rename from test_a.py
rename to test_b.py
CLI rc=0 findings= []
parse: [('test_a.py', 'test_b.py', False, False, True, False, [])]
CHECK PASS rename100 expected ('test_a.py', 'test_b.py', False, False, True, False)
=== new: header lines
diff --git a/test_added.py b/test_added.py
new file mode 100644
--- /dev/null
+++ b/test_added.py
CLI rc=0 findings= []
parse: [(None, 'test_added.py', True, False, False, False, [('+', 'def test_one():', None, 1), ('+', '    assert f(1) == 2', None, 2), ('+', '', None, 3), ('+', '', None, 4), ('+', 'def test_two():', None, 5), ('+', '    assert f(2) == 3', None, 6), ('+', '', None, 7), ('+', '', None, 8), ('+', 'def test_three():', None, 9), ('+', '    assert f(3) == 4', None, 10)])]
CHECK PASS new expected (None, 'test_added.py', True, False, False, False)
=== deleted: header lines
diff --git a/test_gone.py b/test_gone.py
deleted file mode 100644
--- a/test_gone.py
+++ /dev/null
CLI rc=1 findings= [('test-deleted', 'high', 'test_gone.py', 1)]
parse: [('test_gone.py', None, False, True, False, False, [('-', 'def test_one():', 1, None), ('-', '    assert f(1) == 2', 2, None), ('-', '', 3, None), ('-', '', 4, None), ('-', 'def test_two():', 5, None), ('-', '    assert f(2) == 3', 6, None), ('-', '', 7, None), ('-', '', 8, None), ('-', 'def test_three():', 9, None), ('-', '    assert f(3) == 4', 10, None)])]
CHECK PASS deleted expected ('test_gone.py', None, False, True, False, False)
=== binary: header lines
diff --git a/tests_fixture.bin b/tests_fixture.bin
Binary files a/tests_fixture.bin and b/tests_fixture.bin differ
CLI rc=0 findings= []
parse: [('tests_fixture.bin', 'tests_fixture.bin', False, False, False, True, [])]
CHECK PASS binary expected ('tests_fixture.bin', 'tests_fixture.bin', False, False, False, True)
=== nonascii: header lines
diff --git "a/tests/test_sp\303\251c.py" "b/tests/test_sp\303\251c.py"
--- "a/tests/test_sp\303\251c.py"
+++ "b/tests/test_sp\303\251c.py"
CLI rc=1 findings= [('skip-added', 'high', 'tests/test_spéc.py', 6)]
parse: [('tests/test_spéc.py', 'tests/test_spéc.py', False, False, False, False, [('+', 'import pytest', None, 1), ('+', "@pytest.mark.skip(reason='x')", None, 6)])]
CHECK PASS nonascii expected ('tests/test_spéc.py', 'tests/test_spéc.py', False, False, False, False)
=== nonewline: header lines
diff --git a/test_nl.py b/test_nl.py
--- a/test_nl.py
+++ b/test_nl.py
\ No newline at end of file
\ No newline at end of file
CLI rc=1 findings= [('skip-added', 'high', 'test_nl.py', 3), ('expected-changed', 'medium', 'test_nl.py', 5)]
parse: [('test_nl.py', 'test_nl.py', False, False, False, False, [('+', '@pytest.mark.skip(reason="x")', None, 3), ('-', '    assert g() == 1', 4, None), ('+', '    assert g() == 2', None, 5)])]
CHECK PASS nonewline expected ('test_nl.py', 'test_nl.py', False, False, False, False)
rc=0

```

### C11 — falsifiers and restores

```
$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sha256sum /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py | tee /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/diffparse.sha.before
add3ca9900ee10c9c035dae3818ef26cb88a60e359730f68c23a0046c394a25b  /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sed -i 's/out.append(int(s\[i + 1:j\], 8) \& 0xFF)/out.append(int(s[i + 1:j], 10) \& 0xFF)/' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py; grep -n 'int(s\[i + 1:j\]' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py; rm -rf /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/__pycache__; cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b; /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c11_probe.sh 2>&1 | grep -E 'CHECK|findings'; exit ${PIPESTATUS[0]}
68:                out.append(int(s[i + 1:j], 10) & 0xFF)
CLI rc=0 findings= [('expected-changed', 'medium', 'test_new.py', 10)]
CHECK PASS rename expected ('test_old.py', 'test_new.py', False, False, True, False)
CLI rc=0 findings= []
CHECK PASS rename100 expected ('test_a.py', 'test_b.py', False, False, True, False)
CLI rc=0 findings= []
CHECK PASS new expected (None, 'test_added.py', True, False, False, False)
CLI rc=1 findings= [('test-deleted', 'high', 'test_gone.py', 1)]
CHECK PASS deleted expected ('test_gone.py', None, False, True, False, False)
CLI rc=0 findings= []
CHECK PASS binary expected ('tests_fixture.bin', 'tests_fixture.bin', False, False, False, True)
CLI rc=1 findings= [('skip-added', 'high', 'tests/test_sp/�c.py', 6)]
CHECK FAIL nonascii expected ('tests/test_spéc.py', 'tests/test_spéc.py', False, False, False, False)
CLI rc=1 findings= [('skip-added', 'high', 'test_nl.py', 3), ('expected-changed', 'medium', 'test_nl.py', 5)]
CHECK PASS nonewline expected ('test_nl.py', 'test_nl.py', False, False, False, False)
rc=1

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sha256sum -c /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/diffparse.sha.before && cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b && /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c11_probe.sh >/dev/null 2>&1; echo probe_after_restore_rc=$?
/home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py: OK
probe_after_restore_rc=0
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sed -i 's/startswith("rename from ")/startswith("renamX from ")/' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py; rm -rf /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/__pycache__; cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b; /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c11_probe.sh 2>&1 | grep -E 'CHECK FAIL|Traceback|internal error|CRASH'; echo mutant_probe_rc=${PIPESTATUS[0]}
mutant_probe_rc=0
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sed -i 's/startswith("new file mode")/startswith("newX file mode")/' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py; rm -rf /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/__pycache__; cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b; /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c11_probe.sh 2>&1 | grep -E 'CHECK FAIL|Traceback|internal error|CRASH'; echo mutant_probe_rc=${PIPESTATUS[0]}
mutant_probe_rc=0
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sed -i 's/startswith("deleted file mode")/startswith("delX file mode")/' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py; rm -rf /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/__pycache__; cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b; /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c11_probe.sh 2>&1 | grep -E 'CHECK FAIL|Traceback|internal error|CRASH'; echo mutant_probe_rc=${PIPESTATUS[0]}
mutant_probe_rc=0
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sed -i 's/line.startswith("Binary files ") or line.startswith("GIT binary patch")/line.startswith("BinX")/' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py; rm -rf /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/__pycache__; cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b; /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c11_probe.sh 2>&1 | grep -E 'CHECK FAIL|Traceback|internal error|CRASH'; echo mutant_probe_rc=${PIPESTATUS[0]}
CHECK FAIL binary expected ('tests_fixture.bin', 'tests_fixture.bin', False, False, False, True)
mutant_probe_rc=1
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sha256sum -c /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/diffparse.sha.before; sha256sum -c /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/rules.sha.before; sha256sum -c /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/cli.sha.before; rm -rf /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/__pycache__
/home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py: OK
/home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/rules.py: OK
/home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/cli.py: OK
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sed -i 's/cur.is_rename = True/cur.is_rename = False/g' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py; grep -c '= False$' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py; rm -rf /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/__pycache__; cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b; /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c11_probe.sh 2>&1 | grep -E 'CHECK FAIL|Traceback|internal error|CRASH'; echo mutant_probe_rc=${PIPESTATUS[0]}
6
CHECK FAIL rename expected ('test_old.py', 'test_new.py', False, False, True, False)
CHECK FAIL rename100 expected ('test_a.py', 'test_b.py', False, False, True, False)
mutant_probe_rc=1
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sed -i 's/cur.is_new = True/cur.is_new = False/g' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py; grep -c '= False$' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py; rm -rf /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/__pycache__; cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b; /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c11_probe.sh 2>&1 | grep -E 'CHECK FAIL|Traceback|internal error|CRASH'; echo mutant_probe_rc=${PIPESTATUS[0]}
6
CHECK FAIL new expected (None, 'test_added.py', True, False, False, False)
mutant_probe_rc=1
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sed -i 's/cur.is_deleted = True/cur.is_deleted = False/g' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py; grep -c '= False$' /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py; rm -rf /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/__pycache__; cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b; /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c11_probe.sh 2>&1 | grep -E 'CHECK FAIL|Traceback|internal error|CRASH'; echo mutant_probe_rc=${PIPESTATUS[0]}
6
CHECK FAIL deleted expected ('test_gone.py', None, False, True, False, False)
mutant_probe_rc=1
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sha256sum -c /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/diffparse.sha.before; rm -rf /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/__pycache__
/home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py: OK
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) python3 /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/mut_nl.py /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py && rm -rf /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/__pycache__; cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b; /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c11_probe.sh 2>&1 | grep -E 'CHECK FAIL|Traceback|internal error|CRASH'; echo mutant_probe_rc=${PIPESTATUS[0]}
mutated
CHECK FAIL nonewline expected ('test_nl.py', 'test_nl.py', False, False, False, False)
mutant_probe_rc=1
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) sha256sum -c /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/diffparse.sha.before; rm -rf /home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/__pycache__
/home/rajib2k5/dev/test-tamper-guard/src/test_tamper_guard/diffparse.py: OK
rc=0

```

<details><summary>c11_probe.sh</summary>

```
#!/bin/bash
# Real git repos producing each header; run parser + CLI; compare to paths we created.
W=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b
P=/home/rajib2k5/dev/test-tamper-guard
B=$W/c11; rm -rf $B; mkdir -p $B
mk(){ rm -rf $B/$1; mkdir -p $B/$1; cd $B/$1; git init -q; git config user.email p@x; git config user.name p; git config core.quotePath true; }
T='def test_one():
    assert f(1) == 2


def test_two():
    assert f(2) == 3


def test_three():
    assert f(3) == 4
'
# 1 rename with edit
mk rename; printf '%s' "$T" > test_old.py; git add -A; git commit -qm b
git mv test_old.py test_new.py; sed -i 's/f(3) == 4/f(3) == 5/' test_new.py; git commit -qam h
# 2 pure rename (100%)
mk rename100; printf '%s' "$T" > test_a.py; git add -A; git commit -qm b; git mv test_a.py test_b.py; git commit -qm h
# 3 new file
mk new; echo x > README; git add -A; git commit -qm b; printf '%s' "$T" > test_added.py; git add -A; git commit -qm h
# 4 deleted file
mk deleted; printf '%s' "$T" > test_gone.py; echo x > README; git add -A; git commit -qm b; git rm -q test_gone.py; git commit -qm h
# 5 binary
mk binary; printf '\x00\x01\x02' > tests_fixture.bin; git add -A; git commit -qm b; printf '\x00\x09\x08\xff' > tests_fixture.bin; git commit -qam h
# 6 non-ASCII path with core.quotePath=true, add a skip
mk nonascii; mkdir tests; printf '%s' "$T" > "tests/test_spéc.py"; git add -A; git commit -qm b
python3 - <<'PY'
p="tests/test_spéc.py"; s=open(p).read().replace("def test_two", "@pytest.mark.skip(reason='x')\ndef test_two"); open(p,"w").write("import pytest\n"+s)
PY
git commit -qam h
# 7 no trailing newline: old and new last line lack newline, add skip on it
mk nonewline; printf 'import pytest\n\ndef test_z():\n    assert g() == 1' > test_nl.py; git add -A; git commit -qm b
printf 'import pytest\n\n@pytest.mark.skip(reason="x")\ndef test_z():\n    assert g() == 2' > test_nl.py; git commit -qam h
cd $B
fail=0
for s in rename rename100 new deleted binary nonascii nonewline; do
  cd $B/$s
  git diff --no-ext-diff --no-color -M -U3 HEAD~1 HEAD > $B/$s.patch
  echo "=== $s: header lines"
  grep -E '^(diff --git|rename (from|to)|similarity|new file mode|deleted file mode|--- |\+\+\+ |Binary files|\\ No newline)' $B/$s.patch
  out=$(cd $P && PYTHONPATH=src python3 -B -m test_tamper_guard --range HEAD~1..HEAD --format json 2>&1 <&-; echo "cli_rc=$?")
  out2=$(cd $B/$s && PYTHONPATH=$P/src python3 -B -m test_tamper_guard --range HEAD~1..HEAD --format json 2>&1; echo "cli_rc=$?")
  echo "$out2" | python3 -c 'import sys,json; t=sys.stdin.read(); body,rc=t.rsplit("cli_rc=",1); d=json.loads(body); print("CLI rc="+rc.strip(), "findings=", [(f["rule"],f["severity"],f["path"],f["line"]) for f in d["findings"]])' || { echo "CLI output not JSON: $out2"; fail=1; }
  echo "$out2" | grep -q 'Traceback\|internal error' && { echo CRASH; fail=1; }
  PYTHONPATH=$P/src python3 -B - "$s" "$B/$s.patch" <<'PY' || fail=1
import sys
from test_tamper_guard.diffparse import parse_diff
s, patch = sys.argv[1], sys.argv[2]
fds = parse_diff(open(patch, encoding="utf-8").read())
summ = [(f.old_path, f.new_path, f.is_new, f.is_deleted, f.is_rename, f.is_binary,
         [(l.kind, l.text, l.old_no, l.new_no) for h in f.hunks for l in h.lines if l.kind != " "]) for f in fds]
print("parse:", summ)
EXP = {  # (old_path, new_path, is_new, is_deleted, is_rename, is_binary) from what the script created
 "rename":    ("test_old.py", "test_new.py", False, False, True, False),
 "rename100": ("test_a.py", "test_b.py", False, False, True, False),
 "new":       (None, "test_added.py", True, False, False, False),
 "deleted":   ("test_gone.py", None, False, True, False, False),
 "binary":    ("tests_fixture.bin", "tests_fixture.bin", False, False, False, True),
 "nonascii":  ("tests/test_spéc.py", "tests/test_spéc.py", False, False, False, False),
 "nonewline": ("test_nl.py", "test_nl.py", False, False, False, False),
}[s]
ok = len(fds) == 1 and tuple(summ[0][:6]) == EXP
if ok and s == "nonewline":
    texts = [t for (_, t, _, _) in summ[0][6]]
    ok = not any("No newline" in t for t in texts) and ("+", "    assert g() == 2", None, 5) in summ[0][6]
print("CHECK", "PASS" if ok else "FAIL", s, "expected", EXP)
sys.exit(0 if ok else 1)
PY
done
exit $fail
```
</details>

<details><summary>mut_nl.py</summary>

```
import sys
p = sys.argv[1]; s = open(p).read()
old = 'if tag == "\\\\":\n                continue'
assert s.count(old) == 1, s.count(old)
s = s.replace(old, 'if tag == "\\\\":\n                hunk.lines.append(Line("+", body, None, new_no)); continue')
open(p, "w").write(s); print("mutated")
```
</details>

### C12 — tag to SHA resolution

```
$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) git ls-remote https://github.com/actions/checkout 'refs/tags/v7.0.1' 'refs/tags/v7.0.1^{}'
3d3c42e5aac5ba805825da76410c181273ba90b1	refs/tags/v7.0.1
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) git ls-remote https://github.com/actions/setup-python 'refs/tags/v7.1.0' 'refs/tags/v7.1.0^{}'
6d4fd22b20465ccc0f7354476588e8df7c9ca0e0	refs/tags/v7.1.0
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) gh api repos/actions/checkout/git/ref/tags/v7.0.1 --jq '.object.type+" "+.object.sha'; gh api repos/actions/setup-python/git/ref/tags/v7.1.0 --jq '.object.type+" "+.object.sha'
commit 3d3c42e5aac5ba805825da76410c181273ba90b1
commit 6d4fd22b20465ccc0f7354476588e8df7c9ca0e0
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) gh api repos/actions/checkout/commits/3d3c42e5aac5ba805825da76410c181273ba90b1 --jq .sha; gh api repos/actions/setup-python/commits/6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 --jq .sha
3d3c42e5aac5ba805825da76410c181273ba90b1
6d4fd22b20465ccc0f7354476588e8df7c9ca0e0
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) git ls-remote --tags https://github.com/actions/checkout | grep -E 'refs/tags/v7(\.|$)'; echo ---; git ls-remote --tags https://github.com/actions/setup-python | grep -E 'refs/tags/v7(\.|$)'
3d3c42e5aac5ba805825da76410c181273ba90b1	refs/tags/v7
9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0	refs/tags/v7.0.0
3d3c42e5aac5ba805825da76410c181273ba90b1	refs/tags/v7.0.1
---
6d4fd22b20465ccc0f7354476588e8df7c9ca0e0	refs/tags/v7
5fda3b95a4ea91299a34e894583c3862153e4b97	refs/tags/v7.0.0
6d4fd22b20465ccc0f7354476588e8df7c9ca0e0	refs/tags/v7.1.0
rc=0

```

### C13 — Python 3.9 suite, compile, coverage, falsifier

```
$ (cwd=/home/rajib2k5/dev/test-tamper-guard) cd /home/rajib2k5/dev/test-tamper-guard && PYTHONDONTWRITEBYTECODE=1 /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/py39/bin/python -m pytest -q -p no:cacheprovider 2>&1 | tail -15; exit ${PIPESTATUS[0]}
........................................................................ [ 42%]
........................................................................ [ 85%]
........................                                                 [100%]
168 passed in 7.39s
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) cd /home/rajib2k5/dev/test-tamper-guard && PYTHONDONTWRITEBYTECODE=1 /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/py39/bin/python -c 'import ast,sys,pathlib
bad=0
for f in sorted(pathlib.Path("src").rglob("*.py"))+sorted(pathlib.Path("hooks").rglob("*.py")):
    try: compile(f.read_text(), str(f), "exec")
    except SyntaxError as e: bad+=1; print("SYNTAX", f, e)
print("compiled ok under", sys.version.split()[0], "bad=", bad); sys.exit(bad)'
compiled ok under 3.9.25 bad= 0
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) cd /home/rajib2k5/dev/test-tamper-guard && COVERAGE_FILE=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/.cov39 PYTHONDONTWRITEBYTECODE=1 /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/py39/bin/python -m coverage run --source=src,hooks -m pytest -q -p no:cacheprovider 2>&1 | tail -1; COVERAGE_FILE=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/.cov39 /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/py39/bin/python -m coverage report 2>&1 | tail -12
168 passed in 6.92s
Name                                 Stmts   Miss  Cover
--------------------------------------------------------
hooks/pretooluse.py                    114    114     0%
src/test_tamper_guard/__init__.py        1      0   100%
src/test_tamper_guard/__main__.py        3      3     0%
src/test_tamper_guard/cli.py            91      5    95%
src/test_tamper_guard/diffparse.py     178      2    99%
src/test_tamper_guard/engine.py        277      6    98%
src/test_tamper_guard/rules.py         367     14    96%
--------------------------------------------------------
TOTAL                                 1031    144    86%
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c13copy && PYTHONDONTWRITEBYTECODE=1 /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/py39/bin/python -m pytest -q -p no:cacheprovider tests/test_hook.py 2>&1 | tail -1
19 passed in 2.54s
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c13copy && tail -3 src/test_tamper_guard/cli.py; PYTHONDONTWRITEBYTECODE=1 /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/py39/bin/python -m pytest -q -p no:cacheprovider 2>&1 | tail -3; echo py39_rc=${PIPESTATUS[0]}; PYTHONDONTWRITEBYTECODE=1 /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/.venv/bin/python -m pytest -q -p no:cacheprovider 2>&1 | tail -1; echo py312_rc=${PIPESTATUS[0]}

def _probe_310(a: str | None) -> None:
    pass
ERROR tests/test_eval.py - FileNotFoundError: [Errno 2] No such file or direc...
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
2 errors in 0.15s
py39_rc=2
1 error in 0.14s
py312_rc=2
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c13copy && PYTHONDONTWRITEBYTECODE=1 /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/py39/bin/python -m pytest -q -p no:cacheprovider 2>&1 | tail -1; echo unmutated_copy_py39_rc=${PIPESTATUS[0]}
168 passed in 3.96s
unmutated_copy_py39_rc=0
rc=0

$ (cwd=/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b) cd /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/c13copy && tail -3 src/test_tamper_guard/cli.py; PYTHONDONTWRITEBYTECODE=1 /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/py39/bin/python -m pytest -q -p no:cacheprovider 2>&1 | grep -m1 TypeError; PYTHONDONTWRITEBYTECODE=1 /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/py39/bin/python -m pytest -q -p no:cacheprovider 2>&1 | tail -1; echo mutant_py39_rc=${PIPESTATUS[0]}; PYTHONDONTWRITEBYTECODE=1 /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/.venv/bin/python -m pytest -q -p no:cacheprovider 2>&1 | tail -1; echo mutant_py312_rc=${PIPESTATUS[0]}

def _probe_310(a: str | None) -> None:
    pass
E   TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
1 error in 0.14s
mutant_py39_rc=2
168 passed in 2.34s
mutant_py312_rc=0
rc=0

```

### Project tree integrity

```
$ (cwd=/home/rajib2k5/dev/test-tamper-guard) cd /home/rajib2k5/dev/test-tamper-guard && sha256sum -c --quiet /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/tree.sha.before && echo ALL_413_FILES_MATCH; find . -path ./.venv -prune -o -type f -not -path '*/__pycache__/*' -not -path './.pytest_cache/*' -not -path './.ruff_cache/*' -print | wc -l; ls docs/validation
ALL_413_FILES_MATCH
413
channel-a.md
claims-ledger.md
rc=0

```

## env-pin.txt

```
# env-pin for Channel B, 2026-10-30T04:06:53Z
system python3: Python 3.12.3  (used for: PYTHONPATH=src python3 -m test_tamper_guard)
probe venv (/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/.venv):
Python 3.12.13
filelock==4.2.4
fsspec==2026.9.0
iniconfig==2.3.1
jinja2==3.1.6
markupsafe==3.0.3
mpmath==1.3.0
networkx==3.7
numpy==2.5.4
packaging==26.3
pluggy==1.7.0
pygments==2.21.0
pytest==9.2.0
setuptools==78.1.0
sympy==1.14.0
torch==2.15.0+cpu
typing-extensions==4.16.0
py39 venv (/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/py39):
Python 3.9.25
Using Python 3.9.25 environment at: py39
coverage==7.10.7
exceptiongroup==1.3.1
iniconfig==2.1.0
packaging==26.3
pluggy==1.6.0
pygments==2.21.0
pytest==8.4.2
tomli==2.5.0
typing-extensions==4.16.0
node: v22.23.1  jest: 30.5.2
js@1.0.0 /tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/egv-b/js
└── jest@30.5.2

git: git version 2.43.0
uv: uv 0.11.25 (aarch64-unknown-linux-gnu)
gh: gh version 2.96.0 (2026-07-02)
claude CLI: 2.1.296 (Claude Code)
claude-agent-sdk (d.ts inspected): 0.3.195 at ~/.local/lib/node_modules/cline/node_modules/@anthropic-ai/claude-agent-sdk
act: not installed
docker: Docker version 29.6.2, build dfc4efb
uname: Linux 7.0.0-1019-nvidia aarch64
```
