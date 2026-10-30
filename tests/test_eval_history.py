"""scripts/eval_history.py on a real temp repo: first-parent, non-merge commits, findings >= medium."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "eval_history.py"


def _git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@e", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    return subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True, text=True).stdout


def _commit(repo, rel, text, msg):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD").strip()


@pytest.fixture
def history(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    t = "def test_a():\n    assert a() == 1\n"
    _commit(repo, "tests/test_a.py", t, "root")
    _commit(repo, "src/a.py", "x = 1\n", "benign")
    bad = _commit(repo, "tests/test_a.py", "import pytest\n\n\n@pytest.mark.skip\n" + t, "skip it")
    _git(repo, "checkout", "-q", "-b", "side")
    _commit(repo, "tests/test_b.py", "def test_b():\n    assert b() == 2\n", "side work")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    _commit(repo, "src/a.py", "x = 2\n", "benign 2")
    return repo, bad


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def test_reports_flagged_commits_and_a_summary(history):
    repo, bad = history
    r = run(repo, "-n", "10")
    assert r.returncode == 0, r.stderr
    flagged = [ln for ln in r.stdout.splitlines() if ln and not ln.startswith((" ", "commits", "#", "repo"))]
    # side work arrives through a merge: not first-parent, so not listed; the merge itself is skipped.
    assert ([ln.split()[0] for ln in flagged], "commits flagged: 1/4" in r.stdout) == ([bad], True), r.stdout


def test_n_limits_the_commits_scanned(history):
    repo, _ = history
    assert ("commits flagged: 0/1" in run(repo, "-n", "1").stdout, "commits flagged: 1/2" in run(repo, "-n", "2").stdout) == (True, True)


def test_not_a_repo_exits_two(tmp_path):
    assert run(tmp_path, "-n", "1").returncode == 2


def test_shallow_boundary_commit_is_skipped_not_diffed_against_nothing(history, tmp_path):
    repo, bad = history
    clone = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "2", "--no-checkout", "file://%s" % repo, str(clone)],
                   check=True, capture_output=True)
    r = run(clone, "-n", "10")
    # depth 2 holds "benign 2" and the merge; the merge's ... first-parent chain is cut at the boundary.
    assert ("commits flagged: 0/" in r.stdout, "skipped (parent not in this clone): " in r.stdout) == (True, True), r.stdout
