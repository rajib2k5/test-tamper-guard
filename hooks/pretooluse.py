#!/usr/bin/env python3
"""PreToolUse hook: ask before an edit that weakens a test.

Contract (Claude Code PreToolUse):
  stdin  : JSON { tool_name, tool_input, cwd, ... }
  stdout : JSON { hookSpecificOutput: { hookEventName, permissionDecision, permissionDecisionReason } }

Analysis only: reads the target file, applies the edit in memory, diffs old -> new, runs the
engine. It never writes a file, never spawns a process, never runs repo code. Fails OPEN on any
error, except two: when the work on a test file runs past the time budget, or the old or new
content of a test file is over 2 MB, it asks (an edit the guard skips is an edit it lets through
unchecked). Env: TEST_TAMPER_GUARD_MODE = ask (default) | deny |
warn | off; TEST_TAMPER_GUARD_LEVEL = minimum severity (high|medium|low, default medium);
TEST_TAMPER_GUARD_BUDGET_S = seconds for reading, diffing and analysing (default 7, under the
10 s hook timeout; 0 turns the budget off). The budget uses SIGALRM, so it applies on POSIX only.
"""
import difflib
import json
import os
import signal
import sys

MAX_BYTES = 2 * 1024 * 1024
SEVERITY = {"low": 1, "medium": 2, "high": 3}
EDIT_TOOLS = ("Write", "Edit", "MultiEdit")
DEFAULT_BUDGET_S = 7.0


class TooLarge(Exception):
    """The old or new content of a test file is over MAX_BYTES, so the guard cannot analyse it."""


class BudgetExceeded(BaseException):
    """Raised by the SIGALRM handler. A BaseException, so no ``except Exception`` swallows it."""


def _budget_s():
    raw = os.environ.get("TEST_TAMPER_GUARD_BUDGET_S", "").strip()
    try:
        value = float(raw) if raw else DEFAULT_BUDGET_S
    except ValueError:
        return DEFAULT_BUDGET_S
    return value if value == value and value >= 0 else DEFAULT_BUDGET_S  # NaN and negatives: default


def _on_alarm(signum, frame):
    raise BudgetExceeded()


def _start_budget(seconds):
    """Arm a one-shot timer; False when the platform has no SIGALRM or the budget is off."""
    if seconds <= 0 or not hasattr(signal, "setitimer") or not hasattr(signal, "SIGALRM"):
        return False
    signal.signal(signal.SIGALRM, _on_alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    return True


def _stop_budget():
    signal.setitimer(signal.ITIMER_REAL, 0)


def _add_src_to_path():
    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    src = os.path.join(root, "src")
    if not os.path.isdir(src):
        src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def _read_current(path):
    """Return current text ('' if missing), or None if it is too large / unreadable."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return ""
    if size > MAX_BYTES:
        return None
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        return f.read()


def _lf(s):
    return s.replace("\r\n", "\n")


def _apply(old, name, ti):
    """New content after the edit, or None when the edit does not apply.

    ``old`` is already LF-normalised; edit strings are normalised the same way, so a
    CRLF file matches an LF ``old_string``. A non-unique ``old_string`` without
    ``replace_all`` is rejected by Claude Code, so it gives None here too.
    """
    if name == "Write":
        content = ti.get("content")
        return _lf(content) if isinstance(content, str) else None
    edits = ti.get("edits") if name == "MultiEdit" else [ti]
    if not isinstance(edits, list) or not edits:
        return None
    text = old
    for e in edits:
        if not isinstance(e, dict):
            return None
        o, n = e.get("old_string"), e.get("new_string")
        if not isinstance(o, str) or not isinstance(n, str):
            return None
        o, n = _lf(o), _lf(n)
        if o == "":
            if text == "":  # Edit with empty old_string creates a file
                text = n
                continue
            return None
        count = text.count(o)
        if count == 0 or (count > 1 and not e.get("replace_all")):
            return None
        text = text.replace(o, n) if e.get("replace_all") else text.replace(o, n, 1)
    return text


def _diff(rel, old, new):
    body = list(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile="a/" + rel,
            tofile="b/" + rel,
            n=3,
        )
    )
    if not body:
        return ""
    body = [ln if ln.endswith("\n") else ln + "\n\\ No newline at end of file\n" for ln in body]
    return "diff --git a/%s b/%s\n%s" % (rel, rel, "".join(body))


def _findings(abs_path, rel, name, ti, level, analyze_diff):
    """Findings at or above level for the edit ([] when there is nothing to check)."""
    old = _read_current(abs_path)
    if old is None:
        raise TooLarge()
    old = _lf(old)
    new = _apply(old, name, ti)
    if new is None or new == old:
        return []
    if len(new) > MAX_BYTES:
        raise TooLarge()
    diff = _diff(rel, old, new)
    if not diff:
        return []
    return [f for f in analyze_diff(diff) if SEVERITY.get(f.severity, 0) >= level]


def main():
    mode = os.environ.get("TEST_TAMPER_GUARD_MODE", "ask").strip().lower()
    if mode == "off":
        return
    level = SEVERITY.get(os.environ.get("TEST_TAMPER_GUARD_LEVEL", "medium").strip().lower(), 2)

    data = json.loads(sys.stdin.read())
    if not isinstance(data, dict):
        return
    name = data.get("tool_name")
    ti = data.get("tool_input")
    if name not in EDIT_TOOLS or not isinstance(ti, dict):
        return
    file_path = ti.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) and data.get("cwd") else os.getcwd()
    abs_path = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    abs_path = os.path.normpath(abs_path)
    try:
        rel = os.path.relpath(abs_path, cwd)
    except ValueError:
        rel = abs_path
    if rel.startswith(".."):
        rel = abs_path.lstrip("/")
    rel = rel.replace(os.sep, "/")

    _add_src_to_path()
    from test_tamper_guard.engine import analyze_diff
    from test_tamper_guard.rules import is_test_file

    if not is_test_file(rel):
        return
    budget = _budget_s()
    armed = _start_budget(budget)
    too_large = False
    try:
        findings = _findings(abs_path, rel, name, ti, level, analyze_diff)
    except TooLarge:
        findings, too_large = None, True
    except BudgetExceeded:
        findings = None
    finally:
        if armed:
            try:
                _stop_budget()
            except BudgetExceeded:  # fired just as the work ended: the findings are complete
                pass
    if too_large:
        reason = (
            "test-tamper-guard: %s is too large for the guard to analyse (over %d MB), so this "
            "edit was not checked. Look at the test change yourself before proceeding."
            % (rel, MAX_BYTES // (1024 * 1024))
        )
    elif findings is None:
        reason = (
            "test-tamper-guard could not finish checking this edit to %s within %g s, so it was "
            "not checked. Look at the test change yourself before proceeding." % (rel, budget)
        )
    elif not findings:
        return
    else:
        lines = ["test-tamper-guard: this edit looks like it weakens a test."]
        for f in findings:
            lines.append("- [%s] %s %s:%s %s" % (f.severity, f.rule, f.path, f.line, f.message))
        lines.append(
            "Fix the code, not the test. If this test change is intended, say why before proceeding."
        )
        reason = "\n".join(lines)
    if mode == "warn":
        sys.stderr.write(reason + "\n")
        return
    # A budget overrun or a file over the cap is not a finding: it asks even in deny mode.
    decision = "deny" if mode == "deny" and findings else "ask"
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:  # fail open: a buggy guard must not brick the session
        if isinstance(exc, (SystemExit, KeyboardInterrupt)):
            raise
        sys.stderr.write("test-tamper-guard: hook error (ignored): %r\n" % (exc,))
    sys.exit(0)
