#!/usr/bin/env python3
"""Score analyze_diff against fixture dirs.

    eval_fixtures.py [DIR ...] [--json]      (default DIR: fixtures)

A fixture is a directory holding ``diff.patch`` and ``expected.json``. A diff is
"flagged" when it has at least one finding of severity high or medium. A tamper
fixture's expected rule is "hit" only when a finding with that rule id at
severity >= medium exists. Two recall numbers are reported: a tamper fixture is
"detected (any rule)" when it is flagged, and "detected (expected rule)" only
when at least one of its expected rules is hit. Always exits 0: this is a report.
"""

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from test_tamper_guard.engine import analyze_diff
except ImportError:  # running from a checkout without installing
    sys.path.insert(0, os.path.join(_ROOT, "src"))
    from test_tamper_guard.engine import analyze_diff

FLAG_SEVERITIES = ("high", "medium")


def find_fixtures(dirs):
    out = []
    for top in dirs:
        for root, subdirs, files in os.walk(top):
            subdirs.sort()
            if "expected.json" in files and "diff.patch" in files:
                out.append(root)
    return sorted(out)


def evaluate(dirs):
    rows = []
    per_rule = {}
    for fx in find_fixtures(dirs):
        with open(os.path.join(fx, "expected.json"), encoding="utf-8") as fh:
            exp = json.load(fh)
        with open(os.path.join(fx, "diff.patch"), encoding="utf-8", errors="replace") as fh:
            findings = analyze_diff(fh.read())
        strong = sorted({f.rule for f in findings if f.severity in FLAG_SEVERITIES})
        flagged = bool(strong)
        expected_rules = list(exp.get("rules", [])) if exp.get("tamper") else []
        missed = [r for r in expected_rules if r not in strong]
        for r in expected_rules:
            slot = per_rule.setdefault(r, {"hit": 0, "total": 0})
            slot["total"] += 1
            slot["hit"] += r not in missed
        rows.append({
            "fixture": os.path.relpath(fx, _ROOT) if fx.startswith(_ROOT) else fx,
            "tamper": bool(exp.get("tamper")),
            "flagged": flagged,
            "rules_found": sorted({"%s:%s" % (f.rule, f.severity) for f in findings}),
            "missed": missed,
            "expected_hit": bool(expected_rules) and len(missed) < len(expected_rules),
        })
    tamper = [r for r in rows if r["tamper"]]
    legit = [r for r in rows if not r["tamper"]]
    tp = sum(r["flagged"] for r in tamper)
    tp_exp = sum(r["expected_hit"] for r in tamper)
    fp = sum(r["flagged"] for r in legit)
    summary = {
        "tamper_detected": tp,
        "tamper_detected_expected": tp_exp,
        "tamper_total": len(tamper),
        "recall": tp / len(tamper) if tamper else None,
        "recall_expected": tp_exp / len(tamper) if tamper else None,
        "legit_flagged": fp,
        "legit_total": len(legit),
        "false_positive_rate": fp / len(legit) if legit else None,
        "precision": tp / (tp + fp) if (tp + fp) else None,
        "per_rule": dict(sorted(per_rule.items())),
    }
    return {"fixtures": rows, "summary": summary}


def _pct(x):
    return "n/a" if x is None else "%.1f%%" % (100 * x)


def format_report(result):
    rows = result["fixtures"]
    s = result["summary"]
    w = max([len(r["fixture"]) for r in rows] + [7])
    out = ["%-*s  %-8s  %-7s  %s" % (w, "fixture", "expected", "flagged", "rules found / expected rules missed")]
    for r in rows:
        exp = "tamper" if r["tamper"] else "legit"
        ok = "" if r["flagged"] == r["tamper"] else "  <-- WRONG"
        missed = ("  MISSED: " + ",".join(r["missed"])) if r["missed"] else ""
        out.append("%-*s  %-8s  %-7s  %s%s%s" % (w, r["fixture"], exp, "yes" if r["flagged"] else "no",
                                               ",".join(r["rules_found"]) or "-", missed, ok))
    out.append("")
    out.append("tamper detected (any rule):      %d/%d (recall %s)" % (
        s["tamper_detected"], s["tamper_total"], _pct(s["recall"])))
    out.append("tamper detected (expected rule): %d/%d (recall %s)" % (
        s["tamper_detected_expected"], s["tamper_total"], _pct(s["recall_expected"])))
    out.append("legit flagged:                   %d/%d (false-positive rate %s)" % (
        s["legit_flagged"], s["legit_total"], _pct(s["false_positive_rate"])))
    out.append("precision (any rule):            %s" % _pct(s["precision"]))
    out.append("per-rule recall (hit at severity >= medium):")
    for rule, v in s["per_rule"].items():
        out.append("  %-20s %d/%d (%s)" % (rule, v["hit"], v["total"], _pct(v["hit"] / v["total"])))
    return "\n".join(out) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description="Score analyze_diff on fixture dirs (always exits 0).")
    p.add_argument("dirs", nargs="*", default=[os.path.join(_ROOT, "fixtures")])
    p.add_argument("--json", action="store_true", help="machine-readable output")
    a = p.parse_args(argv)
    result = evaluate(a.dirs)
    if a.json:
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
    else:
        sys.stdout.write(format_report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
