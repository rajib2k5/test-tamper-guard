#!/usr/bin/env python3
"""Measure false positives on real history.

    eval_history.py REPO_DIR [-n 100]

For each of the last N first-parent, non-merge commits of REPO_DIR's HEAD, run
the engine on ``git diff C^ C`` (the root commit is diffed against the empty
tree) and print the commit with its findings at severity >= medium, then a
summary. Git runs with an argument list (no shell) and with the same fixed diff
options as the CLI; no code from the repo is run. Exit 0 on success, 2 when git
fails on the repo itself. A commit whose parent is missing (shallow clone) is
reported as skipped.
"""

import argparse
import os
import subprocess
import sys
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from test_tamper_guard.cli import GIT_DIFF
    from test_tamper_guard.engine import analyze_diff
except ImportError:  # running from a checkout without installing
    sys.path.insert(0, os.path.join(_ROOT, "src"))
    from test_tamper_guard.cli import GIT_DIFF
    from test_tamper_guard.engine import analyze_diff

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
FLAG = ("high", "medium")


def _git(repo, args):
    r = subprocess.run(["git", "-C", repo] + args, capture_output=True, shell=False)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def commits(repo, n):
    code, out, err = _git(repo, ["rev-list", "--first-parent", "--no-merges", "-n", str(n), "HEAD"])
    if code != 0:
        raise RuntimeError(err.strip() or "git rev-list failed")
    return out.split()


def shallow_boundary(repo):
    """Commits whose parents a shallow clone cut off (git shows them as parentless)."""
    code, out, _ = _git(repo, ["rev-parse", "--git-path", "shallow"])
    path = out.strip()
    if code != 0 or not path:
        return set()
    path = path if os.path.isabs(path) else os.path.join(repo, path)
    try:
        with open(path, encoding="ascii", errors="replace") as fh:
            return set(fh.read().split())
    except OSError:
        return set()


def commit_diff(repo, sha, boundary=frozenset()):
    """The diff text of sha against its first parent, or None if the parent is not available."""
    if sha in boundary:
        return None  # its real parents are not in this clone: diffing against nothing would be wrong
    code, out, _ = _git(repo, ["rev-parse", "--verify", "--quiet", sha + "^"])
    parent = out.strip() if code == 0 else None
    if parent is None:
        parent = EMPTY_TREE  # a true root commit
    code, out, _ = _git(repo, GIT_DIFF[1:] + [parent, sha, "--"])
    return out if code == 0 else None


def main(argv=None):
    p = argparse.ArgumentParser(description="Run the engine over recent commits of a repo (report only).")
    p.add_argument("repo")
    p.add_argument("-n", type=int, default=100, help="how many first-parent non-merge commits (default 100)")
    a = p.parse_args(argv)
    repo = os.path.abspath(a.repo)
    try:
        shas = commits(repo, a.n)
    except RuntimeError as exc:
        sys.stderr.write("eval_history: %s\n" % exc)
        return 2
    head = _git(repo, ["rev-parse", "HEAD"])[1].strip()
    print("repo %s HEAD %s" % (repo, head))
    flagged = 0
    scanned = 0
    skipped = []
    by_rule = Counter()
    boundary = shallow_boundary(repo)
    for sha in shas:
        diff = commit_diff(repo, sha, boundary)
        if diff is None:
            skipped.append(sha)
            continue
        scanned += 1
        strong = [f for f in analyze_diff(diff) if f.severity in FLAG]
        if not strong:
            continue
        flagged += 1
        subject = _git(repo, ["log", "-1", "--format=%s", sha])[1].strip()
        print("%s %s" % (sha, subject[:72]))
        for f in strong:
            by_rule[f.rule] += 1
            print("    %s %s %s:%d %s" % (f.severity, f.rule, f.path, f.line, f.message[:110]))
    pct = 100.0 * flagged / scanned if scanned else 0.0
    print("commits flagged: %d/%d (%.1f%%)" % (flagged, scanned, pct))
    if skipped:
        print("# skipped (parent not in this clone): %d" % len(skipped))
    if by_rule:
        print("# findings >= medium by rule: " + ", ".join("%s %d" % kv for kv in sorted(by_rule.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
