"""Command line: ``test-tamper-guard [--diff FILE|-] [--range A..B|A...B] ...``.

Exit codes: 0 no finding at or above --fail-on; 1 findings at or above it;
2 usage, input or git error. Git is called with an argument list, never a shell.
"""

import argparse
import json
import subprocess
import sys
from typing import List, Optional

from . import __version__
from .engine import SEVERITY_RANK, Finding, analyze_diff

# Fixed prefixes and quoting: user config (diff.noPrefix, diff.mnemonicPrefix,
# core.quotePath=false, diff.external, color.ui) must not change what the parser reads.
GIT_DIFF = ["git", "-c", "core.quotePath=true", "diff", "--no-ext-diff", "--no-color",
            "--src-prefix=a/", "--dst-prefix=b/", "-M", "-U3"]
FAIL_ON = ("high", "medium", "low", "never")


class UsageError(Exception):
    pass


def escape_data(s: str) -> str:
    """GitHub workflow-command message escaping."""
    return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(s: str) -> str:
    """GitHub workflow-command property escaping."""
    return escape_data(s).replace(":", "%3A").replace(",", "%2C")


def _parse_range(rng: str) -> List[str]:
    """``A..B`` -> [A, B] (the two tips); ``A...B`` -> ["A...B"] (git diffs from the merge base)."""
    if rng.startswith("-"):
        raise UsageError("--range must not start with '-': %r" % rng)
    sep = "..." if rng.count("...") == 1 else ".."
    parts = rng.split(sep)
    if len(parts) != 2 or rng.count("..") != 1 or not all(parts) or any(
            p.startswith(("-", ".")) or p.endswith(".") for p in parts):
        raise UsageError("--range must look like A..B or A...B: %r" % rng)
    return [rng] if sep == "..." else parts


def _git_diff(revs: List[str]) -> str:
    try:
        r = subprocess.run(GIT_DIFF + revs + ["--"], capture_output=True, shell=False)
    except OSError as exc:
        raise UsageError("cannot run git: %s" % exc) from exc
    if r.returncode != 0:
        raise UsageError("git diff failed: %s" % r.stderr.decode("utf-8", "replace").strip())
    return r.stdout.decode("utf-8", "replace")


def _read_diff(src: str) -> str:
    if src == "-":
        data = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read()
    else:
        try:
            with open(src, "rb") as fh:
                data = fh.read()
        except OSError as exc:
            raise UsageError("cannot read %s: %s" % (src, exc)) from exc
    return data.decode("utf-8", "replace") if isinstance(data, bytes) else data


def format_text(findings: List[Finding]) -> str:
    if not findings:
        return "test-tamper-guard: no findings\n"
    out = []
    for f in findings:
        out.append("%s:%d: %s %s: %s\n    %s\n" % (f.path, f.line, f.severity, f.rule, f.message, f.evidence))
    counts = {s: sum(1 for f in findings if f.severity == s) for s in ("high", "medium", "low")}
    out.append("test-tamper-guard: %d finding(s) (high %d, medium %d, low %d)\n"
               % (len(findings), counts["high"], counts["medium"], counts["low"]))
    return "".join(out)


def format_json(findings: List[Finding]) -> str:
    counts = {s: sum(1 for f in findings if f.severity == s) for s in ("high", "medium", "low")}
    return json.dumps({"version": __version__, "findings": [f.to_dict() for f in findings], "counts": counts},
                      indent=2) + "\n"


def format_github(findings: List[Finding]) -> str:
    out = []
    for f in findings:
        cmd = "error" if f.severity == "high" else "warning"
        title = "test-tamper-guard %s (%s)" % (f.rule, f.severity)
        out.append("::%s file=%s,line=%d,title=%s::%s\n" % (
            cmd, escape_property(f.path), f.line, escape_property(title),
            escape_data("%s\n%s" % (f.message, f.evidence)),
        ))
    return "".join(out)


FORMATTERS = {"text": format_text, "json": format_json, "github": format_github}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="test-tamper-guard",
        description="Flag diffs that weaken tests instead of fixing the code.",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--diff", metavar="FILE", help="read a unified diff from FILE, or '-' for stdin")
    src.add_argument("--range", metavar="A..B", help="analyse 'git diff A B'; A...B diffs B against the merge base")
    p.add_argument("--format", choices=sorted(FORMATTERS), default="text")
    p.add_argument("--fail-on", choices=FAIL_ON, default="high",
                   help="exit 1 when a finding is at or above this severity (default: high)")
    p.add_argument("--version", action="version", version="%(prog)s " + __version__)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.diff is not None:
            text = _read_diff(args.diff)
        elif args.range is not None:
            text = _git_diff(_parse_range(args.range))
        else:
            text = _git_diff(["HEAD"])
    except UsageError as exc:
        sys.stderr.write("test-tamper-guard: %s\n" % exc)
        return 2
    try:
        findings = analyze_diff(text)
    except Exception as exc:  # never a traceback for untrusted input; report and exit 2
        sys.stderr.write("test-tamper-guard: internal error: %r\n" % (exc,))
        return 2
    sys.stdout.write(FORMATTERS[args.format](findings))
    if args.fail_on == "never":
        return 0
    limit = SEVERITY_RANK[args.fail_on]
    return 1 if any(SEVERITY_RANK[f.severity] >= limit for f in findings) else 0
