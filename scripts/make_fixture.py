#!/usr/bin/env python3
"""Make a fixture diff from real git.

    make_fixture.py BEFORE_DIR AFTER_DIR OUT_PATCH [--work-dir DIR]

Copies BEFORE_DIR into a fresh repo, commits it, replaces the tree with
AFTER_DIR, stages everything, and writes ``git diff -M HEAD`` to OUT_PATCH.
BEFORE_DIR may be empty (every file is new).
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

_ENV = {
    "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
}


def _git(repo, *args):
    env = dict(os.environ, **_ENV)
    r = subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), r.stderr.decode("utf-8", "replace")))
    return r.stdout.decode("utf-8")


def _copy_tree(src, dst):
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        for name in files:
            out_dir = os.path.join(dst, rel)
            os.makedirs(out_dir, exist_ok=True)
            shutil.copy2(os.path.join(root, name), os.path.join(out_dir, name))


def _clear_tree(repo):
    for name in os.listdir(repo):
        if name == ".git":
            continue
        p = os.path.join(repo, name)
        if os.path.isdir(p):
            shutil.rmtree(p)
        else:
            os.remove(p)


def make_patch(before_dir, after_dir, work_dir=None):
    """Return the ``git diff -M HEAD`` text for before -> after."""
    repo = tempfile.mkdtemp(prefix="ttg-fixture-", dir=work_dir)
    try:
        _git(repo, "init", "-q", "-b", "main")
        _copy_tree(before_dir, repo)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "--allow-empty", "-m", "before")
        _clear_tree(repo)
        _copy_tree(after_dir, repo)
        _git(repo, "add", "-A")
        return _git(repo, "diff", "--no-ext-diff", "--no-color", "-M", "HEAD")
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("before_dir")
    p.add_argument("after_dir")
    p.add_argument("out_patch")
    p.add_argument("--work-dir", default=None, help="where to create the scratch repo")
    a = p.parse_args(argv)
    patch = make_patch(a.before_dir, a.after_dir, a.work_dir)
    with open(a.out_patch, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(patch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
