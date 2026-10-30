"""Behaviour tests for hooks/pretooluse.py: run it as a subprocess, as Claude Code does."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "pretooluse.py"

ORIGINAL = '''import pytest


def test_total():
    assert compute() == pytest.approx(1.0, rel=1e-9)


def test_other():
    assert other() == 2
'''


def run_hook(payload, env_extra=None, raw=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("TEST_TAMPER_GUARD_")}
    env.update(env_extra or {})
    data = raw if raw is not None else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOK)], input=data, capture_output=True, text=True, env=env, timeout=30
    )


def decision(proc):
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return None
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    return out


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calc.py").write_text(ORIGINAL)
    (tmp_path / "calc.py").write_text("def compute():\n    return 1\n")
    return tmp_path


def edit(repo, rel, old, new, **kw):
    return {
        "tool_name": "Edit",
        "cwd": str(repo),
        "tool_input": {"file_path": rel, "old_string": old, "new_string": new, **kw},
    }


def test_edit_adding_skip_asks(repo):
    p = edit(repo, "tests/test_calc.py", "def test_other():", "@pytest.mark.skip\ndef test_other():")
    out = decision(run_hook(p))
    assert out["permissionDecision"] == "ask"
    assert "skip-added" in out["permissionDecisionReason"]
    assert "tests/test_calc.py" in out["permissionDecisionReason"]


def test_edit_loosening_tolerance_asks(repo):
    p = edit(repo, "tests/test_calc.py", "rel=1e-9", "rel=1e-2")
    out = decision(run_hook(p))
    assert out["permissionDecision"] == "ask"
    assert "tolerance-loosened" in out["permissionDecisionReason"]


def test_write_deleting_a_test_asks(repo):
    content = ORIGINAL.split("def test_other")[0].rstrip() + "\n"
    p = {"tool_name": "Write", "cwd": str(repo),
         "tool_input": {"file_path": str(repo / "tests" / "test_calc.py"), "content": content}}
    out = decision(run_hook(p))
    assert out["permissionDecision"] == "ask"
    assert "test-deleted" in out["permissionDecisionReason"]


def test_multiedit_adding_skip_asks(repo):
    p = {"tool_name": "MultiEdit", "cwd": str(repo), "tool_input": {
        "file_path": "tests/test_calc.py",
        "edits": [{"old_string": "def test_other():", "new_string": "@pytest.mark.skip\ndef test_other():"}]}}
    assert decision(run_hook(p))["permissionDecision"] == "ask"


def test_edit_on_non_test_file_is_silent(repo):
    p = edit(repo, "calc.py", "return 1", "return 2")
    assert decision(run_hook(p)) is None


def test_benign_new_test_is_silent(repo):
    p = edit(repo, "tests/test_calc.py", "def test_other():",
             "def test_new():\n    assert 1 + 1 == 2\n\n\ndef test_other():")
    assert decision(run_hook(p)) is None


def test_mode_off_is_silent(repo):
    p = edit(repo, "tests/test_calc.py", "def test_other():", "@pytest.mark.skip\ndef test_other():")
    assert decision(run_hook(p, {"TEST_TAMPER_GUARD_MODE": "off"})) is None


def test_mode_deny_denies(repo):
    p = edit(repo, "tests/test_calc.py", "def test_other():", "@pytest.mark.skip\ndef test_other():")
    out = decision(run_hook(p, {"TEST_TAMPER_GUARD_MODE": "deny"}))
    assert out["permissionDecision"] == "deny"


def test_mode_warn_gives_no_decision(repo):
    p = edit(repo, "tests/test_calc.py", "def test_other():", "@pytest.mark.skip\ndef test_other():")
    proc = run_hook(p, {"TEST_TAMPER_GUARD_MODE": "warn"})
    assert decision(proc) is None
    assert "skip-added" in proc.stderr


def test_level_high_ignores_medium_findings(repo):
    p = edit(repo, "tests/test_calc.py", "assert other() == 2", "assert other() == 3")
    assert decision(run_hook(p, {"TEST_TAMPER_GUARD_LEVEL": "high"})) is None
    assert decision(run_hook(p, {"TEST_TAMPER_GUARD_LEVEL": "medium"}))["permissionDecision"] == "ask"


@pytest.mark.parametrize("raw", ["", "not json", "[1,2]", '{"tool_name": "Edit"}', '{"tool_input": 5}'])
def test_malformed_stdin_fails_open(raw):
    proc = run_hook(None, raw=raw)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_old_string_not_found_is_silent(repo):
    p = edit(repo, "tests/test_calc.py", "THIS TEXT IS NOT THERE", "@pytest.mark.skip")
    assert decision(run_hook(p)) is None


def test_replace_all_applies_to_every_occurrence(repo):
    path = repo / "tests" / "test_calc.py"
    path.write_text(ORIGINAL + "\n\ndef test_third():\n    assert compute() == pytest.approx(1.0, rel=1e-9)\n")
    p = edit(repo, "tests/test_calc.py", "rel=1e-9", "rel=1e-2", replace_all=True)
    reason = decision(run_hook(p))["permissionDecisionReason"]
    assert reason.count("tolerance-loosened") >= 2


def test_hook_does_not_modify_files(repo):
    path = repo / "tests" / "test_calc.py"
    p = edit(repo, "tests/test_calc.py", "rel=1e-9", "rel=1e-2")
    run_hook(p)
    assert path.read_text() == ORIGINAL


def test_edit_on_a_crlf_file_with_lf_old_string_still_asks(repo):
    path = repo / "tests" / "test_calc.py"
    path.write_bytes(ORIGINAL.replace("\n", "\r\n").encode())
    p = edit(repo, "tests/test_calc.py", "def test_other():\n    assert other() == 2",
             "@pytest.mark.skip\ndef test_other():\n    assert other() == 2")
    out = decision(run_hook(p))
    assert out["permissionDecision"] == "ask"
    assert "skip-added" in out["permissionDecisionReason"]


def test_edit_on_a_crlf_file_with_crlf_old_string_asks(repo):
    path = repo / "tests" / "test_calc.py"
    path.write_bytes(ORIGINAL.replace("\n", "\r\n").encode())
    p = edit(repo, "tests/test_calc.py", "def test_other():\r\n", "@pytest.mark.skip\r\ndef test_other():\r\n")
    assert decision(run_hook(p))["permissionDecision"] == "ask"


def test_non_unique_old_string_without_replace_all_gives_no_decision(repo):
    path = repo / "tests" / "test_calc.py"
    path.write_text(ORIGINAL + "\n\ndef test_third():\n    assert compute() == pytest.approx(1.0, rel=1e-9)\n")
    p = edit(repo, "tests/test_calc.py", "rel=1e-9", "rel=1e-2")
    assert decision(run_hook(p)) is None


def test_unique_old_string_without_replace_all_changes_only_that_place(repo):
    path = repo / "tests" / "test_calc.py"
    path.write_text(ORIGINAL + "\n\ndef test_third():\n    assert compute() == pytest.approx(1.0, rel=1e-9)\n")
    p = edit(repo, "tests/test_calc.py", "def test_third():\n    assert compute() == pytest.approx(1.0, rel=1e-9)",
             "def test_third():\n    assert compute() == pytest.approx(1.0, rel=1e-2)")
    reason = decision(run_hook(p))["permissionDecisionReason"]
    assert reason.count("tolerance-loosened") == 1


# ------------------------------------------------------------------ time budget


def _big_write(repo):
    """A Write that rewrites a 2,000-line test file: far more than 10 ms of diff and analysis."""
    path = repo / "tests" / "test_big.py"
    path.write_text("".join("def test_%d():\n    assert f(%d) == %d\n\n\n" % (i, i, i) for i in range(500)))
    content = "".join("def test_%d():\n    assert f(%d) == %d\n\n\n" % (i, i, i + 1) for i in range(500))
    return {"tool_name": "Write", "cwd": str(repo), "tool_input": {"file_path": str(path), "content": content}}


def test_budget_exceeded_on_a_test_file_asks_and_says_the_guard_did_not_finish(repo):
    out = decision(run_hook(_big_write(repo), {"TEST_TAMPER_GUARD_BUDGET_S": "0.01"}))
    assert (out["permissionDecision"], "could not finish" in out["permissionDecisionReason"]) == ("ask", True)


def test_budget_exceeded_in_deny_mode_still_only_asks(repo):
    env = {"TEST_TAMPER_GUARD_BUDGET_S": "0.01", "TEST_TAMPER_GUARD_MODE": "deny"}
    assert decision(run_hook(_big_write(repo), env))["permissionDecision"] == "ask"


def test_budget_exceeded_in_warn_mode_gives_no_decision(repo):
    proc = run_hook(_big_write(repo), {"TEST_TAMPER_GUARD_BUDGET_S": "0.01", "TEST_TAMPER_GUARD_MODE": "warn"})
    assert (decision(proc), "could not finish" in proc.stderr) == (None, True)


def test_budget_exceeded_in_off_mode_gives_no_decision(repo):
    proc = run_hook(_big_write(repo), {"TEST_TAMPER_GUARD_BUDGET_S": "0.01", "TEST_TAMPER_GUARD_MODE": "off"})
    assert (decision(proc), proc.stderr) == (None, "")


def test_default_budget_lets_a_big_edit_finish_with_its_findings(repo):
    out = decision(run_hook(_big_write(repo)))
    assert ("expected-changed" in out["permissionDecisionReason"], "could not finish" in out["permissionDecisionReason"]) == (True, False)


def test_budget_on_a_non_test_file_gives_no_decision(repo):
    (repo / "big.py").write_text("x = 1\n" * 20000)
    p = {"tool_name": "Write", "cwd": str(repo), "tool_input": {"file_path": str(repo / "big.py"), "content": "x = 2\n" * 20000}}
    assert decision(run_hook(p, {"TEST_TAMPER_GUARD_BUDGET_S": "0.01"})) is None


def test_bad_budget_value_falls_back_to_the_default(repo):
    out = decision(run_hook(_big_write(repo), {"TEST_TAMPER_GUARD_BUDGET_S": "soon"}))
    assert "could not finish" not in out["permissionDecisionReason"]


# ---------------------------------------- files over the size cap (review 3, S1)


BIG = 2 * 1024 * 1024 + 10


def _big_old(repo, rel="tests/test_huge.py"):
    path = repo / rel
    path.write_text("def test_a():\n    assert f() == 1\n" + "#" * BIG + "\n")
    return {"tool_name": "Edit", "cwd": str(repo),
            "tool_input": {"file_path": rel, "old_string": "def test_a():", "new_string": "@pytest.mark.skip\ndef test_a():"}}


def _big_new(repo, rel="tests/test_calc.py"):
    content = ORIGINAL.replace("def test_other", "@pytest.mark.skip\ndef test_other") + "#" * BIG + "\n"
    return {"tool_name": "Write", "cwd": str(repo), "tool_input": {"file_path": rel, "content": content}}


@pytest.mark.parametrize("make", [_big_old, _big_new], ids=["old-too-large", "new-too-large"])
def test_edit_of_a_test_file_over_the_size_cap_asks(repo, make):
    out = decision(run_hook(make(repo)))
    assert (out["permissionDecision"], "too large" in out["permissionDecisionReason"]) == ("ask", True)


def test_file_over_the_size_cap_in_deny_mode_still_only_asks(repo):
    assert decision(run_hook(_big_new(repo), {"TEST_TAMPER_GUARD_MODE": "deny"}))["permissionDecision"] == "ask"


def test_file_over_the_size_cap_in_warn_mode_writes_to_stderr(repo):
    proc = run_hook(_big_new(repo), {"TEST_TAMPER_GUARD_MODE": "warn"})
    assert (decision(proc), "too large" in proc.stderr) == (None, True)


def test_file_over_the_size_cap_in_off_mode_gives_no_decision(repo):
    proc = run_hook(_big_new(repo), {"TEST_TAMPER_GUARD_MODE": "off"})
    assert (decision(proc), proc.stderr) == (None, "")


@pytest.mark.parametrize("make", [_big_old, _big_new], ids=["old-too-large", "new-too-large"])
def test_non_test_file_over_the_size_cap_gives_no_decision(repo, make):
    assert decision(run_hook(make(repo, "big_module.py"))) is None
