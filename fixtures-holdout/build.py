#!/usr/bin/env python3
"""Regenerate every fixture: sources -> before/ after/ expected.json -> diff.patch (real `git diff -M --cached`)."""
import json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from author_part1 import PYTEST_TAMPER
from author_part2 import JEST_TAMPER
from author_part3 import LEGIT

WORK = Path("/tmp/claude-1000/-home-rajib2k5-dev-test-tamper-guard/4e1434eb-fc7d-4b66-8e14-5c863325b2fa/scratchpad/holdout-work")
ENV = dict(os.environ, GIT_AUTHOR_NAME="h", GIT_AUTHOR_EMAIL="h@x", GIT_COMMITTER_NAME="h",
           GIT_COMMITTER_EMAIL="h@x", GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")


def git(cwd, *a, out=False):
    r = subprocess.run(["git", *a], cwd=cwd, env=ENV, check=True, capture_output=True, text=True)
    return r.stdout if out else None


def write_tree(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text.lstrip("\n"))


def build(kind, fx):
    d = HERE / kind / fx["slug"]
    if d.exists():
        shutil.rmtree(d)
    write_tree(d / "before", fx["before"])
    write_tree(d / "after", fx["after"])
    (d / "expected.json").write_text(json.dumps(
        {"tamper": kind == "tamper", "rules": fx["rules"], "framework": fx["framework"], "note": fx["note"]},
        indent=2) + "\n")
    repo = WORK / kind / fx["slug"]
    if repo.exists():
        shutil.rmtree(repo)
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    shutil.copytree(d / "before", repo, dirs_exist_ok=True)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "before")
    for p in list(repo.rglob("*")):  # replace working tree with the after state
        if p.is_file() and ".git" not in p.relative_to(repo).parts:
            p.unlink()
    shutil.copytree(d / "after", repo, dirs_exist_ok=True)
    git(repo, "add", "-A")
    patch = git(repo, "diff", "-M", "--cached", out=True)
    assert patch.strip(), fx["slug"]
    (d / "diff.patch").write_text(patch)


if __name__ == "__main__":
    for fx in PYTEST_TAMPER + JEST_TAMPER:
        build("tamper", fx)
    for fx in LEGIT:
        build("legit", fx)
    print("built", len(PYTEST_TAMPER) + len(JEST_TAMPER), "tamper,", len(LEGIT), "legit")
