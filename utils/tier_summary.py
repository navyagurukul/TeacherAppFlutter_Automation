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
from utils import build_info, school_enrolment
from utils.app_version import label_with_source
from utils.slack_full_summary import _load_cases

# Tier order is the order they must run in: each is a wider net than the last.
TIER_ORDER = ["sanity", "smoke", "regression"]

TIER_INTENT = {
    "sanity": "is the build usable at all",
    "smoke": "do the main happy paths work",
    "regression": "full coverage except `heavy`",
}

# Plain-English line per test, so the report says what was checked. A test not
# listed here falls back to its name with underscores turned into spaces.
DESCRIPTIONS = {
    "test_login_screen_loads": "Login screen opens (Sign in, LOG IN, REGISTER shown)",
    "test_login_shows_app_version": "Login screen shows the app version",
    "test_login_or_register_reaches_home": "Log in with school + mobile reaches the home dashboard",
    "test_login_requires_school": "LOG IN without a school shows 'Please select a school'",
    "test_login_requires_mobile": "LOG IN without a mobile shows 'Mobile number is required'",
    "test_login_rejects_short_mobile": "5-digit mobile is rejected ('Enter a valid 10-digit number')",
    "test_bottom_nav_opens_each_tab": "Bottom tab '{param}' opens its screen",
    "test_home_shows_enrolment_counts": "Home shows Registered / Remaining student counts",
    "test_full_smoke_journey": "Full journey: login, every home box, every tab, logout",
    "test_lesson_pdf_opens_in_viewer": "Lesson-plan PDF opens in the PDF viewer",
    "test_lesson_video_plays_seeks_and_all_languages":
        "Lesson video plays, seeks, and plays in every language",
    "test_open_all_pdfs_and_videos_every_class": "Every class: open every lesson PDF and video",
    "test_catalogue_not_empty": "Lesson catalogue has classes and materials",
    "test_all_pdfs_load": "Every lesson PDF link loads",
    "test_all_videos_load": "Every lesson video link loads",
    "test_all_in_pdf_links_load": "Every link inside the PDFs loads",
}

ICON = {"pass": "✅", "fail": "❌", "skip": "⏭️"}


def describe(name: str) -> str:
    base, _, param = name.partition("[")
    param = param.rstrip("]")
    text = DESCRIPTIONS.get(base)
    if text is None:
        text = base.removeprefix("test_").replace("_", " ").capitalize()
        return f"{text} [{param}]" if param else text
    return text.replace("{param}", param) if "{param}" in text else (
        f"{text} [{param}]" if param else text)


def tier_report(tier: str, path: str | None) -> dict:
    """Parse one tier's junit into its numbers and per-test results."""
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
        # (state, description, failure message) in execution order
        "tests": [(c[3], describe(c[1]), c[4]) for c in cases],
    }


def tier_lines(rep: dict) -> list[str]:
    """One tier: headline, then every test with its own pass/fail mark."""
    tier = rep["tier"].capitalize()
    intent = TIER_INTENT.get(rep["tier"], "")
    if not rep["ran"]:
        return [f"*{tier}* ⤼ not run  —  _{intent}_"]

    failed = rep["failed"]
    icon = "✅" if not failed else "❌"
    counts = f"{rep['passed']}/{rep['total']} passed"
    if failed:
        counts += f", {len(failed)} failed"
    if rep["skipped"]:
        counts += f", {rep['skipped']} skipped"
    lines = [f"*{tier}* {icon} {counts}  •  {rep['runtime']:.0f}s  —  _{intent}_"]
    for state, text, msg in rep["tests"]:
        line = f"      {ICON[state]} {text}"
        if state == "fail" and msg:
            line += f"\n            ↳ _{msg[:140]}_"
        lines.append(line)
    return lines


def version_check(info: dict | None) -> str:
    """Compare the version the login screen displayed with the version
    installed on the device. A mismatch means the screen and the package
    disagree (stale footer, wrong build installed)."""
    from utils.app_version import _from_captured

    shown = _from_captured()
    installed = (info or {}).get("version_name")
    if shown and installed:
        if shown == installed:
            return f"✅ login screen shows V{shown} = installed V{installed}"
        return f"❌ login screen shows V{shown} but installed is V{installed}"
    if installed:
        return f"⚠️ installed V{installed}; login-screen version not captured"
    if shown:
        return f"⚠️ login screen shows V{shown}; installed version not read"
    return "⚠️ no version read (device not reached)"


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

    info = build_info.load()
    lines = [
        f"*Teacher App QA — Sanity / Smoke / Regression* ({now})   {status}",
        f"Build tested: *{build_info.summary(info)}*",
        f"App version: *{label_with_source()}*",
        f"Version check: {version_check(info)}",
        f"School: *{SCHOOL_NAME}*  •  Mobile: *{TEACHER_MOBILE}*",
        f"Enrolment: {school_enrolment.label_with_source()}",
    ]
    if info and info.get("device"):
        lines.append(f"Device: {info['device']}")
    lines.append("")
    for rep in reports:
        lines += tier_lines(rep)
        lines.append("")
    if missing:
        lines.append(f"⚠️ Not run: {', '.join(missing)} — this run does not cover them.")
    return "\n".join(lines).rstrip(), total_failed


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
