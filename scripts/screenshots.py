#!/usr/bin/env python3
"""Build the README screenshots in docs/images/ from real runs of the tool.

Run from the repository root:

    uv run --with rich --with playwright python scripts/screenshots.py

It builds a neutral demo repository in /tmp/demo-test-tamper-guard, runs the real commands there,
and renders each result as an SVG terminal shot (rich). Shot 5 is a crop of the
GitHub Actions annotations panel (Playwright). Every image is scanned for private
data before it is saved. The script raises if it finds any.

Needs: uv, git, python3, and a Chromium build in ~/.cache/ms-playwright.
Writes only to /tmp/demo-test-tamper-guard and docs/images/. It never touches the global git config.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.text import Text

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "images"
DEMO = Path("/tmp/demo-test-tamper-guard")
WORK = DEMO / "pricing"
VENV = DEMO / ".venv"
GIT_URL = "git+https://github.com/rajib2k5/test-tamper-guard"
RUN_URL = "https://github.com/rajib2k5/test-tamper-guard/actions/runs/41012534929"
CHECK_RUN_ID = "123921405986"
MAX_BYTES = 500 * 1024
WIDTH = 100

ENV = {
    "HOME": str(DEMO),
    "PATH": f"{VENV}/bin:{Path.home()}/.local/bin:/usr/local/bin:/usr/bin:/bin",
    "VIRTUAL_ENV": str(VENV),
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "LANG": "C.UTF-8",
}

# Privacy scan. The public URL and the repo name are the only allowed uses of the owner name.
ALLOWED = "github.com/rajib2k5/test-tamper-guard"
LEAKS = [
    r"/home/", r"/Users/", r"/root/", r"[A-Za-z]:\\Users\\", r"rajib", r"@gmail", r"gh[pousr]_", r"github_pat_",
    r"(?<![A-Za-z0-9])sk-", r"AKIA",
]


def scan(text, label):
    """Raise if text holds anything private."""
    cleaned = text.replace(ALLOWED, "")
    for pat in LEAKS:
        m = re.search(pat, cleaned, re.IGNORECASE if pat == r"rajib" else 0)
        if m:
            ctx = cleaned[max(0, m.start() - 40): m.end() + 40].replace("\n", " ")
            raise RuntimeError(f"privacy leak in {label}: /{pat}/ near {ctx!r}")


def run(cmd, cwd=None, stdin=None, env=None):
    p = subprocess.run(
        cmd, cwd=cwd, env=env or ENV, input=stdin, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    return p.returncode, p.stdout


def git(*args):
    rc, out = run(["git", "-c", "user.name=demo", "-c", "user.email=demo@example.com",
                   "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false", *args], cwd=WORK)
    if rc != 0:
        raise RuntimeError(f"git {args} failed: {out}")
    return out


# ---------------------------------------------------------------- demo repo

PRICING_PY = '''"""Small pricing helpers."""


def bond_price(face, coupon_rate, ytm, years):
    """Price of an annual-coupon bond."""
    coupon = face * coupon_rate
    pv = sum(coupon / (1 + ytm) ** t for t in range(1, years + 1))
    return pv + face / (1 + ytm) ** years


def total_return(start, end):
    """Simple return between two prices."""
    return (end - start) / start
'''

PY_TEST = '''import pytest

from pricing import bond_price, total_return


def test_bond_price_at_par():
    assert bond_price(100, 0.05, 0.05, 10) == pytest.approx(100.0, rel=1e-9)


def test_bond_price_discount():
    assert bond_price(100, 0.04, 0.06, 10) == pytest.approx(92.6399, rel=1e-6)


def test_total_return():
    assert total_return(100.0, 110.0) == pytest.approx(0.10, rel=1e-9)
'''

JS_TEST = '''const { bondPrice } = require("../src/pricing");

describe("bondPrice", () => {
  test("prices a par bond at face value", () => {
    expect(bondPrice(100, 0.05, 0.05, 10)).toBeCloseTo(100, 6);
  });
});
'''


def write(rel, text):
    path = WORK / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_demo_repo():
    git("init", "-q")
    write("pricing.py", PRICING_PY)
    write("tests/test_pricing.py", PY_TEST)
    write("tests/pricing.test.js", JS_TEST)
    git("add", "-A")
    git("commit", "-q", "-m", "Add pricing helpers and tests")
    base = git("rev-parse", "HEAD").strip()

    # Tamper commit on main: loosen a tolerance, skip a test, change an expected value.
    t = PY_TEST.replace("100.0, rel=1e-9", "100.0, rel=1e-2")
    t = t.replace("92.6399", "95.0")
    t = t.replace("def test_total_return", "@pytest.mark.skip\ndef test_total_return")
    write("tests/test_pricing.py", t)
    write("tests/pricing.test.js", JS_TEST.replace("100, 6)", "100, 1)"))
    git("commit", "-q", "-am", "Make the tests pass")

    # Legit change on its own branch: tighten a tolerance and add a test.
    git("checkout", "-q", "-b", "legit", base)
    t = PY_TEST.replace("92.6399, rel=1e-6", "92.6399, rel=1e-8")
    t += '''

def test_zero_coupon_bond():
    assert bond_price(100, 0.0, 0.05, 10) == pytest.approx(61.3913, rel=1e-6)
'''
    write("tests/test_pricing.py", t)
    git("commit", "-q", "-am", "Tighten tolerance and add a zero-coupon test")


# ---------------------------------------------------------------- rendering


def render(name, title, steps):
    """steps: list of (command_line_or_None, output_text). Saves docs/images/<name>.svg."""
    console = Console(record=True, width=WIDTH, force_terminal=True, color_system="truecolor",
                      file=open(os.devnull, "w"))
    plain = []
    for cmd, output in steps:
        if cmd is not None:
            console.print(Text("$ ", style="bold green") + Text(cmd, style="bold"))
            plain.append("$ " + cmd)
        if output:
            console.print(Text(output.rstrip("\n")))
            plain.append(output)
    text = "\n".join(plain)
    scan(text, name)
    scan(title, name + " title")
    svg = console.export_svg(title=title)
    scan(svg, name + " svg")
    path = OUT / f"{name}.svg"
    path.write_text(svg)
    return path


def trim(output, keep=12):
    lines = output.rstrip("\n").split("\n")
    return output if len(lines) <= keep else "...\n" + "\n".join(lines[-keep:])


# ---------------------------------------------------------------- shots


def shot_install():
    DEMO_ENV = ENV
    rc, out = run(["uv", "venv", "-q", str(VENV)], cwd=DEMO)
    if rc != 0:
        raise RuntimeError(out)
    shown = "uv pip install git+https://github.com/rajib2k5/test-tamper-guard"
    rc, out = run(["uv", "pip", "install", GIT_URL], cwd=DEMO, env=DEMO_ENV)
    used_git = rc == 0
    if not used_git:
        print(f"WARNING: git-URL install failed, falling back to local path:\n{out}")
        rc, out = run(["uv", "pip", "install", str(REPO)], cwd=DEMO)
        if rc != 0:
            raise RuntimeError(out)
        out = out.replace(str(REPO), "test-tamper-guard")
        shown = "uv pip install test-tamper-guard"
    rc2, helptext = run(["test-tamper-guard", "--help"], cwd=DEMO)
    if rc2 != 0:
        raise RuntimeError(helptext)
    render("01-install", "Install", [
        (shown, trim(out)),
        ("test-tamper-guard --help", helptext),
    ])
    return used_git


def shot_cli(name, title, branch):
    git("checkout", "-q", branch)
    cmd = "test-tamper-guard --range HEAD~1..HEAD"
    rc, out = run(cmd.split(), cwd=WORK)
    render(name, title, [(cmd, out), ("echo $?", str(rc))])
    return rc


def shot_hook():
    git("checkout", "-q", "legit")
    target = str(WORK / "tests" / "test_pricing.py")
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "cwd": str(WORK),
        "tool_input": {
            "file_path": target,
            "old_string": "def test_total_return():",
            "new_string": "@pytest.mark.skip\ndef test_total_return():",
        },
    }
    stdin = json.dumps(payload)
    rc, out = run(["/usr/bin/python3", str(REPO / "hooks" / "pretooluse.py")], cwd=WORK, stdin=stdin)
    if rc != 0:
        raise RuntimeError(out)
    pretty = json.dumps(json.loads(out), indent=2)
    render("04-claude-hook", "Claude Code hook", [
        ("python3 hooks/pretooluse.py < edit.json", pretty),
    ])
    return pretty


def chromium_path():
    found = glob.glob(str(Path.home() / ".cache/ms-playwright/chromium_headless_shell-*/*/headless_shell"))
    found += glob.glob(str(Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux/chrome"))
    return found[0] if found else None


def shot_annotations_png():
    """Crop the annotations panel of the real CI run. Returns the path, or None on failure."""
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=chromium_path())
            page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
            page.goto(RUN_URL, wait_until="networkidle", timeout=45000)
            handle = page.evaluate_handle(
                """() => {
                    const h = [...document.querySelectorAll('h2,h3')].find(
                        e => e.textContent.trim() === 'Annotations');
                    if (!h) return null;
                    let e = h;
                    while (e && !e.querySelector('annotation-message, .annotation--contracted')) e = e.parentElement;
                    return e;
                }""").as_element()
            if handle is None:
                browser.close()
                return None
            # Expand the "Show more" buttons so the text is complete.
            for b in handle.query_selector_all("button:has-text('Show more')"):
                try:
                    b.click(timeout=2000)
                except Exception:
                    pass
            text = handle.inner_text()
            scan(text, "05 page text")
            path = OUT / "05-action-annotations.png"
            handle.screenshot(path=str(path))
            browser.close()
            return path
    except Exception as exc:  # fall back to the SVG path
        print(f"WARNING: annotations page not usable: {exc}")
        return None


def shot_annotations_svg():
    # The annotations API is public for public repos; gh uses GH_TOKEN or its own login if set.
    env = dict(os.environ)
    rc, out = run(["gh", "api", f"repos/rajib2k5/test-tamper-guard/check-runs/{CHECK_RUN_ID}/annotations",
                   "--jq", '.[] | "\\(.path):\\(.start_line) \\(.annotation_level) \\(.title)\\n    \\(.message)"'],
                  env=env)
    if rc != 0:
        raise RuntimeError("gh api failed")
    wf = (REPO / ".github/workflows/tamper-guard.yml").read_text()
    render("05-action-annotations", "GitHub Action annotations", [
        ("cat .github/workflows/tamper-guard.yml", wf),
        ("gh api .../check-runs/<id>/annotations", out),
    ])
    return OUT / "05-action-annotations.svg"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if DEMO.exists():
        shutil.rmtree(DEMO)
    DEMO.mkdir(parents=True)
    WORK.mkdir()

    used_git = shot_install()
    build_demo_repo()
    rc_tamper = shot_cli("02-flag-tampered", "Flag a tampered test", "main")
    rc_legit = shot_cli("03-legit-passes", "A legitimate change passes", "legit")
    shot_hook()
    png = shot_annotations_png()
    path5 = "png" if png else "svg"
    if not png:
        png = shot_annotations_svg()

    print(f"git-URL install worked: {used_git}")
    print(f"exit codes: tampered={rc_tamper} legit={rc_legit}")
    print(f"shot 5 path: {path5}")
    for f in sorted(OUT.glob("0*")):
        size = f.stat().st_size
        print(f"{f.name}: {size / 1024:.1f} KB")
        if size > MAX_BYTES:
            raise RuntimeError(f"{f.name} is over 500 KB")


if __name__ == "__main__":
    sys.exit(main())
