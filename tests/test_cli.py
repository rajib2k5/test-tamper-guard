"""CLI behaviour: inputs, formats, --fail-on exit codes, git integration."""

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from _diff import modify

from test_tamper_guard import cli

ROOT = Path(__file__).resolve().parents[1]

HIGH_DIFF = modify(
    "tests/test_a.py",
    "def test_a():\n    assert a() == 1\n",
    "import pytest\n\n\n@pytest.mark.skip(reason='flaky, 100%')\ndef test_a():\n    assert a() == 1\n",
)
MEDIUM_DIFF = modify("tests/test_a.py", "def test_a():\n    assert a() == 1\n", "def test_a():\n    assert a() == 2\n")
CLEAN_DIFF = modify("src/a.py", "x = 1\n", "x = 2\n")


def run(args, stdin_text=None, monkeypatch=None, capsys=None):
    if stdin_text is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    code = cli.main(args)
    out, err = capsys.readouterr()
    return code, out, err


def test_clean_diff_from_stdin_exits_zero(monkeypatch, capsys):
    code, _, _ = run(["--diff", "-"], CLEAN_DIFF, monkeypatch, capsys)
    assert code == 0


def test_high_finding_exits_one_with_default_fail_on(monkeypatch, capsys):
    code, _, _ = run(["--diff", "-"], HIGH_DIFF, monkeypatch, capsys)
    assert code == 1


def test_medium_finding_exits_zero_with_default_fail_on(monkeypatch, capsys):
    code, _, _ = run(["--diff", "-"], MEDIUM_DIFF, monkeypatch, capsys)
    assert code == 0


def test_medium_finding_exits_one_with_fail_on_medium(monkeypatch, capsys):
    code, _, _ = run(["--diff", "-", "--fail-on", "medium"], MEDIUM_DIFF, monkeypatch, capsys)
    assert code == 1


def test_fail_on_never_exits_zero_on_high(monkeypatch, capsys):
    code, _, _ = run(["--diff", "-", "--fail-on", "never"], HIGH_DIFF, monkeypatch, capsys)
    assert code == 0


def test_diff_read_from_file(tmp_path, capsys):
    p = tmp_path / "x.patch"
    p.write_text(HIGH_DIFF)
    assert cli.main(["--diff", str(p)]) == 1


def test_missing_diff_file_exits_two(tmp_path, capsys):
    assert cli.main(["--diff", str(tmp_path / "nope.patch")]) == 2


def test_unknown_option_exits_two(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--bogus"])
    assert e.value.code == 2


def test_range_starting_with_dash_is_rejected(capsys):
    code = cli.main(["--range=--output=/tmp/x..HEAD"])
    _, err = capsys.readouterr()
    assert (code, "range" in err) == (2, True)


def test_range_without_two_dots_is_rejected(capsys):
    assert cli.main(["--range", "HEAD"]) == 2


def test_range_with_dash_second_part_is_rejected(capsys):
    assert cli.main(["--range", "HEAD..-x"]) == 2


def test_json_format_lists_findings(monkeypatch, capsys):
    code, out, _ = run(["--diff", "-", "--format", "json"], HIGH_DIFF, monkeypatch, capsys)
    data = json.loads(out)
    assert [(f["rule"], f["severity"], f["path"]) for f in data["findings"]] == [("skip-added", "high", "tests/test_a.py")]


def test_json_finding_has_the_contract_keys(monkeypatch, capsys):
    _, out, _ = run(["--diff", "-", "--format", "json"], HIGH_DIFF, monkeypatch, capsys)
    (f,) = json.loads(out)["findings"]
    assert sorted(f) == ["evidence", "line", "message", "path", "rule", "severity"]


def test_text_format_names_path_line_and_rule(monkeypatch, capsys):
    _, out, _ = run(["--diff", "-"], HIGH_DIFF, monkeypatch, capsys)
    assert "tests/test_a.py:4: high skip-added:" in out


def test_github_format_uses_error_for_high(monkeypatch, capsys):
    _, out, _ = run(["--diff", "-", "--format", "github"], HIGH_DIFF, monkeypatch, capsys)
    assert out.startswith("::error file=tests/test_a.py,line=4,title=")


def test_github_format_uses_warning_for_medium(monkeypatch, capsys):
    _, out, _ = run(["--diff", "-", "--format", "github"], MEDIUM_DIFF, monkeypatch, capsys)
    assert out.startswith("::warning file=tests/test_a.py,line=2,title=")


def test_github_message_escapes_percent_and_newline(monkeypatch, capsys):
    _, out, _ = run(["--diff", "-", "--format", "github"], HIGH_DIFF, monkeypatch, capsys)
    line = out.splitlines()[0]
    msg = line.split("::", 2)[2]
    assert ("100%25" in msg, "%0A" in msg, "100%," in msg) == (True, True, False)


def test_github_property_escapes_comma_and_colon():
    assert cli.escape_property("a,b:c%\n") == "a%2Cb%3Ac%25%0A"


def test_github_data_escapes_only_percent_cr_lf():
    assert cli.escape_data("a,b:c%\r\n") == "a,b:c%25%0D%0A"


def test_github_annotation_escapes_a_path_with_comma(monkeypatch, capsys):
    diff = MEDIUM_DIFF.replace("tests/test_a.py", "tests/test_a,b.py")
    _, out, _ = run(["--diff", "-", "--format", "github"], diff, monkeypatch, capsys)
    assert out.startswith("::warning file=tests/test_a%2Cb.py,line=2,")


# ----------------------------------------------------------------- real git


def _git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@e", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    return subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_a():\n    assert a() == 1\n\n\ndef test_b():\n    assert b() == 2\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "one")
    (tmp_path / "tests" / "test_a.py").write_text("def test_a():\n    assert a() == 1\n")
    _git(tmp_path, "commit", "-q", "-am", "two")
    return tmp_path


def test_range_runs_git_diff_between_commits(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    code = cli.main(["--range", "HEAD~1..HEAD", "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert (code, [f["rule"] for f in data["findings"]]) == (1, ["test-deleted"])


def test_default_diffs_working_tree_against_head(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    (repo / "tests" / "test_a.py").write_text("import pytest\n\n\n@pytest.mark.xfail\ndef test_a():\n    assert a() == 1\n")
    code = cli.main(["--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert (code, [f["rule"] for f in data["findings"]]) == (1, ["skip-added"])


def test_unknown_revision_exits_two(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    assert cli.main(["--range", "nope..HEAD"]) == 2


def test_outside_a_git_repo_exits_two(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    assert cli.main([]) == 2


def test_module_entry_point_runs(repo):
    r = subprocess.run([sys.executable, "-m", "test_tamper_guard", "--range", "HEAD~1..HEAD"], cwd=repo,
                       capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
    assert (r.returncode, "test-deleted" in r.stdout) == (1, True)


# ------------------------------------------------- merge-base ranges (A...B)


@pytest.fixture
def behind(tmp_path):
    """A PR branch cut from main; main then gains a test the branch does not have."""
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_a():\n    assert a() == 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    _git(tmp_path, "checkout", "-q", "-b", "pr")
    (tmp_path / "src.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "pr work")
    _git(tmp_path, "checkout", "-q", "main")
    (tmp_path / "tests" / "test_a.py").write_text("def test_a():\n    assert a() == 1\n\n\ndef test_new():\n    assert n() == 2\n")
    _git(tmp_path, "commit", "-q", "-am", "main gains a test")
    return tmp_path


def test_three_dot_range_ignores_changes_made_on_base_after_the_branch_point(behind, monkeypatch, capsys):
    monkeypatch.chdir(behind)
    code = cli.main(["--range", "main...pr", "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert (code, data["findings"]) == (0, [])


def test_two_dot_range_still_diffs_the_two_tips(behind, monkeypatch, capsys):
    monkeypatch.chdir(behind)
    code = cli.main(["--range", "main..pr", "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert (code, [f["rule"] for f in data["findings"]]) == (1, ["test-deleted"])


@pytest.mark.parametrize("rng", ["-x...HEAD", "HEAD...-x", "...HEAD", "HEAD...", "A....B", "A..B...C", "A...B..C"])
def test_bad_three_dot_ranges_are_rejected(rng, capsys):
    assert cli.main(["--range=" + rng]) == 2


@pytest.mark.parametrize("rng", ["A..--output=x", "A...--output=x", "A..-x", "A...-x"])
def test_right_side_of_a_range_starting_with_a_dash_is_rejected_before_git_runs(rng, monkeypatch):
    # Review 2 mutant: p.startswith(("-", ".")) -> p.startswith(".") survived, because git
    # also failed on "HEAD..-x". "--output=x" as a git argument would write a file.
    def no_git(*a, **k):
        raise AssertionError("git must not run for %r" % rng)

    monkeypatch.setattr(cli.subprocess, "run", no_git)
    with pytest.raises(cli.UsageError):
        cli._parse_range(rng)
    assert cli.main(["--range", rng]) == 2


def test_parse_range_passes_three_dot_as_one_git_argument():
    assert (cli._parse_range("a...b"), cli._parse_range("a..b")) == (["a...b"], ["a", "b"])


def _action_script():
    """The composite action's ``run: |`` block, as bash will see it."""
    lines = (ROOT / "action.yml").read_text().splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == "run: |") + 1
    indent = len(lines[start]) - len(lines[start].lstrip())
    body = []
    for ln in lines[start:]:
        if ln.strip() and len(ln) - len(ln.lstrip()) < indent:
            break
        body.append(ln[indent:])
    return "\n".join(body) + "\n"


def test_action_script_on_a_pr_behind_base_reports_nothing(behind):
    base = _git(behind, "rev-parse", "main").strip()
    head = _git(behind, "rev-parse", "pr").strip()
    env = dict(os.environ, BASE=base, HEAD=head, FAIL_ON="high", PYTHON=sys.executable, GITHUB_ACTION_PATH=str(ROOT))
    r = subprocess.run(["bash", "-c", _action_script()], cwd=behind, env=env, capture_output=True, text=True)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def _run_action(repo, base, head):
    env = dict(os.environ, BASE=base, HEAD=head, FAIL_ON="high", PYTHON=sys.executable, GITHUB_ACTION_PATH=str(ROOT))
    return subprocess.run(["bash", "-c", _action_script()], cwd=repo, env=env, capture_output=True, text=True)


def test_action_on_a_push_event_checks_the_last_commit(repo):
    # Push events have no pull_request.base.sha: BASE is empty. Before review 2 the range was
    # "...SHA" and the step failed with exit 2.
    r = _run_action(repo, "", _git(repo, "rev-parse", "HEAD").strip())
    assert (r.returncode, "test-deleted" in r.stdout) == (1, True), r.stderr


def test_action_on_a_push_of_the_first_commit_prints_a_notice_and_passes(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "root")
    r = _run_action(tmp_path, "", _git(tmp_path, "rev-parse", "HEAD").strip())
    assert (r.returncode, r.stdout.startswith("::notice"), r.stderr) == (0, True, "")


def _two_commit_repo(path):
    path.mkdir(exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    (path / "a.py").write_text("x = 1\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "one")
    (path / "a.py").write_text("x = 2\n")
    _git(path, "commit", "-q", "-am", "two")
    return path


def test_action_on_a_push_in_a_shallow_clone_fails_and_asks_for_full_history(tmp_path):
    # Review 3 (S2): actions/checkout fetches depth 1 by default. HEAD~1 is then missing,
    # and the step used to pass with "no base commit", so nothing was checked.
    src = _two_commit_repo(tmp_path / "src")
    subprocess.run(["git", "clone", "-q", "--depth", "1", src.resolve().as_uri(), str(tmp_path / "shallow")],
                   check=True, capture_output=True)
    shallow = tmp_path / "shallow"
    r = _run_action(shallow, "", _git(shallow, "rev-parse", "HEAD").strip())
    assert (r.returncode, r.stdout.startswith("::error"), "fetch-depth: 0" in r.stdout) == (2, True, True)


def test_action_on_a_pr_in_a_shallow_clone_without_the_base_fails(tmp_path):
    src = _two_commit_repo(tmp_path / "src")
    base = _git(src, "rev-parse", "HEAD~1").strip()
    subprocess.run(["git", "clone", "-q", "--depth", "1", src.resolve().as_uri(), str(tmp_path / "shallow")],
                   check=True, capture_output=True)
    shallow = tmp_path / "shallow"
    r = _run_action(shallow, base, _git(shallow, "rev-parse", "HEAD").strip())
    assert (r.returncode, "fetch-depth: 0" in r.stdout) == (2, True)


def test_action_on_a_push_of_a_normal_commit_in_a_full_clone_runs_the_check(tmp_path):
    repo = _two_commit_repo(tmp_path)
    r = _run_action(repo, "", _git(repo, "rev-parse", "HEAD").strip())
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


# ------------------------------------------- user git config cannot change paths


@pytest.fixture
def odd_prefix_repo(tmp_path):
    """Test file under a top-level directory named b/ (what diff.noPrefix would strip)."""
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "b" / "tests").mkdir(parents=True)
    (tmp_path / "b" / "tests" / "test_a.py").write_text("def test_a():\n    assert a() == 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "one")
    (tmp_path / "b" / "tests" / "test_a.py").write_text("import pytest\n\n\n@pytest.mark.skip\ndef test_a():\n    assert a() == 1\n")
    _git(tmp_path, "commit", "-q", "-am", "two")
    return tmp_path


@pytest.mark.parametrize("key", ["diff.noPrefix", "diff.mnemonicPrefix"])
@pytest.mark.parametrize("args", [["--range", "HEAD~1..HEAD"], ["--range", "HEAD~1...HEAD"]])
def test_paths_are_exact_whatever_the_diff_prefix_config(odd_prefix_repo, monkeypatch, capsys, key, args):
    _git(odd_prefix_repo, "config", key, "true")
    monkeypatch.chdir(odd_prefix_repo)
    cli.main(args + ["--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert [(f["rule"], f["path"]) for f in data["findings"]] == [("skip-added", "b/tests/test_a.py")]


def test_working_tree_paths_are_exact_with_mnemonic_prefix(odd_prefix_repo, monkeypatch, capsys):
    _git(odd_prefix_repo, "config", "diff.mnemonicPrefix", "true")
    (odd_prefix_repo / "b" / "tests" / "test_a.py").write_text("def test_z():\n    assert z() == 1\n")
    monkeypatch.chdir(odd_prefix_repo)
    cli.main(["--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert {f["path"] for f in data["findings"]} == {"b/tests/test_a.py"}


def test_git_is_called_with_fixed_prefixes_and_no_external_diff(monkeypatch):
    seen = []

    class R:
        returncode, stdout, stderr = 0, b"", b""

    monkeypatch.setattr(cli.subprocess, "run", lambda argv, **kw: seen.append((argv, kw)) or R())
    cli.main(["--range", "a..b"])
    argv, kw = seen[0]
    assert (argv[:3], kw.get("shell")) == (["git", "-c", "core.quotePath=true"], False)
    assert {"--no-ext-diff", "--no-color", "--src-prefix=a/", "--dst-prefix=b/"} <= set(argv)
    assert argv[-3:] == ["a", "b", "--"]
