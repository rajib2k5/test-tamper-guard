"""scripts/eval_fixtures.py: scoring rules, and the dev-set regression bar."""

import importlib.util
import json
from pathlib import Path

from _diff import modify

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("eval_fixtures", ROOT / "scripts" / "eval_fixtures.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)

SKIP = modify("tests/test_a.py", "def test_a():\n    assert a() == 1\n",
              "import pytest\n\n\n@pytest.mark.skip\ndef test_a():\n    assert a() == 1\n")
SKIP_LINKED = SKIP.replace("@pytest.mark.skip", "@pytest.mark.skip(reason='see #12')")
CHANGED = modify("tests/test_a.py", "def test_a():\n    assert a() == 1\n", "def test_a():\n    assert a() == 2\n")
CLEAN = modify("src/a.py", "x = 1\n", "x = 2\n")


def _fixture(root, kind, slug, diff, rules):
    d = root / kind / slug
    d.mkdir(parents=True)
    (d / "diff.patch").write_text(diff)
    (d / "expected.json").write_text(json.dumps(
        {"tamper": kind == "tamper", "rules": rules, "framework": "pytest", "note": "n"}))


def test_scores_recall_fp_and_precision(tmp_path):
    _fixture(tmp_path, "tamper", "a", SKIP, ["skip-added"])
    _fixture(tmp_path, "tamper", "b", CLEAN, ["test-deleted"])
    _fixture(tmp_path, "legit", "c", CHANGED, [])
    _fixture(tmp_path, "legit", "d", CLEAN, [])
    s = ev.evaluate([str(tmp_path)])["summary"]
    assert (s["tamper_detected"], s["tamper_total"], s["legit_flagged"], s["legit_total"], s["precision"]) == (1, 2, 1, 2, 0.5)


def test_low_severity_finding_does_not_count_as_flagged(tmp_path):
    _fixture(tmp_path, "tamper", "a", SKIP_LINKED, ["skip-added"])
    s = ev.evaluate([str(tmp_path)])["summary"]
    assert (s["tamper_detected"], s["per_rule"]["skip-added"]) == (0, {"hit": 0, "total": 1})


def test_expected_rule_missed_is_reported_per_fixture(tmp_path):
    _fixture(tmp_path, "tamper", "a", SKIP, ["skip-added", "test-deleted"])
    (row,) = ev.evaluate([str(tmp_path)])["fixtures"]
    assert (row["flagged"], row["missed"]) == (True, ["test-deleted"])


def test_detection_by_an_expected_rule_is_counted_separately(tmp_path):
    _fixture(tmp_path, "tamper", "a", SKIP, ["skip-added"])
    _fixture(tmp_path, "tamper", "b", SKIP, ["test-deleted"])  # flagged, but not by its expected rule
    s = ev.evaluate([str(tmp_path)])["summary"]
    assert (s["tamper_detected"], s["tamper_detected_expected"], s["recall_expected"]) == (2, 1, 0.5)


def test_report_prints_both_detection_numbers(tmp_path):
    _fixture(tmp_path, "tamper", "a", SKIP, ["skip-added"])
    _fixture(tmp_path, "tamper", "b", SKIP, ["test-deleted"])
    text = ev.format_report(ev.evaluate([str(tmp_path)]))
    assert ("tamper detected (any rule):      2/2" in text, "tamper detected (expected rule): 1/2" in text) == (True, True)


# --------------------------------------------------- regression bar on fixtures/


def test_dev_fixture_set_meets_the_recall_and_false_positive_bar():
    # Measured on fixtures/ after review round 2: 45/45 tamper (any rule and expected rule), 2/24 legit.
    # Both are the price of the review-2 tightening: legit/08 changes a module constant (TAX_RATE),
    # not a function the test names, so expected-changed is no longer down-graded; legit/15 has
    # ``// WEB-1182: ...`` with no tracker word, so its skip is no longer down-graded.
    s = ev.evaluate([str(ROOT / "fixtures")])["summary"]
    flagged = [r["fixture"] for r in ev.evaluate([str(ROOT / "fixtures")])["fixtures"] if not r["tamper"] and r["flagged"]]
    assert s["tamper_total"] >= 45 and s["legit_total"] >= 24
    assert (s["recall"], s["recall_expected"], [f.rsplit("/", 1)[-1] for f in flagged]) == (
        1.0, 1.0, ["08-py-behaviour-change-with-source", "15-js-skip-with-linked-issue"])


def test_dev_fixture_set_hits_every_expected_rule():
    s = ev.evaluate([str(ROOT / "fixtures")])["summary"]
    missed = {r: v for r, v in s["per_rule"].items() if v["hit"] != v["total"]}
    assert missed == {}
