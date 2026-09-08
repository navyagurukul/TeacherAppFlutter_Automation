"""Post one Slack message covering a tiered run — sanity, then smoke, then
regression — that says for each tier what it actually executed.

Where slack_full_summary.py reports a single run as one number, this reports the
three tiers side by side and *names the tests each tier ran*, so the message
answers "what was covered?" and not only "did it pass?".

    python -m utils.tier_summary sanity=reports/junit_sanity.xml \
                                 smoke=reports/junit_smoke.xml \
                                 regression=reports/junit_regression.xml

Add `--dry-run` to print the message without posting — importing this module
pulls in config.settings, which loads .env, so SLACK_WEBHOOK_URL is set even on a
local preview and an unguarded run would post to the real channel.

A tier whose file is missing is reported as "not run" rather than passing
silently — a tier that never executed must never read as green. Exit code is
non-zero when any tier had failures, so a workflow can gate on it.
"""
from __future__ import annotations

import datetime
import os
import sys

import requests

from data.test_data import SCHOOL_NAME, TEACHER_MOBILE
from utils import school_enrolment
from utils.app_version import label_with_source
from utils.slack_full_summary import _load_cases, _node_id

# Tier order is the order they must run in: each is a wider net than the last.
TIER_ORDER = ["sanity", "smoke", "regression"]

TIER_INTENT = {
    "sanity": "is the build usable at all",
    "smoke": "do the main happy paths work",
    "regression": "full coverage except `heavy`",
}

# How many executed test names to name per tier before summarising the rest.
NAMED_LIMIT = 12


def _short(classname: str, name: str) -> str:
    """'tests.test_login' + 'test_login_reaches_home[Home]' -> a compact label."""
    node = _node_id(classname, name)
    return node.split("::", 1)[-1] if "::" in node else node


def _dedupe(names: list[str]) -> list[str]:
    """Collapse parametrised cases ('test_nav[Home]', 'test_nav[Class]') to one
    entry with a count, so a tier's line lists scenarios rather than repeats."""
    counts: dict[str, int] = {}
    for n in names:
        base = n.split("[", 1)[0]
        counts[base] = counts.get(base, 0) + 1
    return [f"{b} (x{c})" if c > 1 else b for b, c in counts.items()]


def tier_report(tier: str, path: str | None) -> dict:
    """Parse one tier's junit into the numbers and the executed-test list."""
    if not path or not os.path.isfile(path):
        return {"tier": tier, "ran": False}
    cases = list(_load_cases(path))
    if not cases:
        return {"tier": tier, "ran": False}
    return {
        "tier": tier,
        "ran": True,
        "total": len(cases),
        "passed": sum(1 for c in cases if c[3] == "pass"),
        "failed": [c for c in cases if c[3] == "fail"],
        "skipped": sum(1 for c in cases if c[3] == "skip"),
        "runtime": sum(c[2] for c in cases),
        "did": _dedupe([_short(c[0], c[1]) for c in cases if c[3] != "skip"]),
    }


def tier_lines(rep: dict) -> list[str]:
    """The block for one tier: headline, what it did, and any failures."""
    tier = rep["tier"].capitalize()
    intent = TIER_INTENT.get(rep["tier"], "")
    if not rep["ran"]:
        return [f"*{tier}* ⤼ not run  —  _{intent}_"]

    failed = rep["failed"]
    icon = "✅" if not failed else "❌"
    head = (
        f"*{tier}* {icon} {rep['passed']}/{rep['total']}  •  {rep['runtime']:.0f}s"
        f"  —  _{intent}_"
    )
    did = rep["did"]
    shown = ", ".join(did[:NAMED_LIMIT])
    if len(did) > NAMED_LIMIT:
        shown += f", +{len(did) - NAMED_LIMIT} more"
    lines = [head, f"        did: {shown or '(nothing executed)'}"]
    if rep["skipped"]:
        lines.append(f"        skipped: {rep['skipped']}")
    if failed:
        names = ", ".join(_short(c[0], c[1]) for c in failed[:6])
        if len(failed) > 6:
            names += f", +{len(failed) - 6} more"
        lines.append(f"        failed: {names}")
    return lines


def build_message(paths: dict[str, str]) -> tuple[str, int]:
    reports = [tier_report(t, paths.get(t)) for t in TIER_ORDER]
    ran = [r for r in reports if r["ran"]]
    total_failed = sum(len(r["failed"]) for r in ran)
    missing = [r["tier"] for r in reports if not r["ran"]]

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if not ran:
        status = "⚠️ NOTHING RAN"
    elif total_failed:
        status = "❌ FAIL"
    elif missing:
        status = "⚠️ PARTIAL"
    else:
        status = "✅ PASS"

    lines = [
        f"*Teacher App QA — Sanity / Smoke / Regression* ({now})   {status}",
        f"App version: *{label_with_source()}*",
        f"Account: Mobile: *{TEACHER_MOBILE}*  •  School: *{SCHOOL_NAME}*",
        f"Enrolment: {school_enrolment.label_with_source()}",
        "",
    ]
    for rep in reports:
        lines += tier_lines(rep)
    if missing:
        lines += ["", f"⚠️ Not run: {', '.join(missing)} — this run does not cover them."]
    return "\n".join(lines), total_failed


def main() -> int:
    # The report contains emoji; a Windows console (cp1252) would crash on print.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    dry_run = "--dry-run" in sys.argv[1:]
    paths: dict[str, str] = {}
    for arg in sys.argv[1:]:
        if "=" not in arg:
            continue
        tier, path = arg.split("=", 1)
        tier = tier.strip().lower()
        if tier in TIER_ORDER:
            paths[tier] = path.strip()
    if not paths:
        print("usage: python -m utils.tier_summary sanity=<junit> smoke=<junit> regression=<junit>")
        return 0

    text, failed = build_message(paths)
    url = "" if dry_run else os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        why = "--dry-run" if dry_run else "SLACK_WEBHOOK_URL not set"
        print(f"[tier_summary] {why} — printing instead of posting:\n")
        print(text)
    else:
        requests.post(url, json={"text": text}, timeout=30).raise_for_status()
        print("[tier_summary] posted to Slack.")
        print(text)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
