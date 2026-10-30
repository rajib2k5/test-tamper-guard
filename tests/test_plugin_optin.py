"""Config/contract checks for the opt-in constraint (docs/DESIGN.md "Constraints").

These are NOT behaviour tests: they read repo files and assert on their text/structure.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_hooks_json_registers_only_pretooluse_write_edit_multiedit():
    cfg = json.loads((ROOT / "hooks" / "hooks.json").read_text())
    assert list(cfg["hooks"]) == ["PreToolUse"]
    entries = cfg["hooks"]["PreToolUse"]
    assert len(entries) == 1
    assert entries[0]["matcher"] == "Write|Edit|MultiEdit"
    assert len(entries[0]["hooks"]) == 1
    h = entries[0]["hooks"][0]
    assert h["command"] == 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/pretooluse.py"'
    assert h["timeout"] == 10


def test_repo_registers_no_claude_settings_hooks():
    for name in ("settings.json", "settings.local.json"):
        p = ROOT / ".claude" / name
        if p.exists():
            assert "hooks" not in json.loads(p.read_text())


def test_no_install_time_hooks():
    assert not (ROOT / "setup.py").exists()
    text = (ROOT / "pyproject.toml").read_text()
    assert ".claude" not in text
    scripts = re.search(r"\[project\.scripts\](.*?)(?:\n\[|\Z)", text, re.S)
    assert scripts is None or ".claude" not in scripts.group(1)
    assert "cmdclass" not in text


def _code_files():
    for d in ("src", "hooks"):
        for p in (ROOT / d).rglob("*.py"):
            yield p


def test_sources_never_touch_claude_settings():
    for p in _code_files():
        text = p.read_text()
        assert "settings.json" not in text, p
        assert "settings.local.json" not in text, p
        assert not re.search(r"expanduser\([^)]*\.claude|Path\.home\(\)[^\n]*\.claude|~/\.claude", text), p


def test_hook_script_has_no_write_or_subprocess():
    text = (ROOT / "hooks" / "pretooluse.py").read_text()
    assert not re.search(r"open\([^)]*[\"'][wax+][b+]?[\"']", text)
    assert not re.search(r"\bsubprocess\b|os\.system|os\.popen|\.write_text|\.write_bytes|os\.exec|os\.spawn", text)
