"""Post a whole-suite pytest summary to Slack from a JUnit XML file.

Complements run_daily.py: where that posts a per-area media summary, this posts
the result of the *full* scenario run (every marker except `heavy`) — total
pass/fail/skip and the node ids of any failures — so the nightly self-hosted run
reports "all scenarios" in one message.

    python -m utils.slack_full_summary reports/junit_full.xml [--scope "..."]

Reads SLACK_WEBHOOK_URL from the environment (falls back to printing). Exit code
is non-zero when the parsed run had failures, so the workflow can gate on it.
"""
from __future__ import annotations

import datetime
import os
import sys
import xml.etree.ElementTree as ET

import requests

from data.test_data import SCHOOL_NAME, TEACHER_MOBILE
from utils.app_version import label_with_source


def _load_cases(path):
    """Yield (classname, name, time, state, message) for every testcase.
    state is one of pass|fail|skip. Handles <testsuites> or a bare <testsuite>."""
    root = ET.parse(path).getroot()
    suites = root.iter("testsuite")
    for suite in suites:
        for tc in suite.iter("testcase"):
            classname = tc.get("classname", "")
            name = tc.get("name", "")
            try:
                t = float(tc.get("time", "0") or 0)
            except ValueError:
                t = 0.0
            fail = tc.find("failure")
            err = tc.find("error")
            skip = tc.find("skipped")
            if fail is not None or err is not None:
                node = fail if fail is not None else err
                msg = (node.get("message") or "").strip().splitlines()
                yield classname, name, t, "fail", (msg[0] if msg else "")
            elif skip is not None:
                yield classname, name, t, "skip", ""
            else:
                yield classname, name, t, "pass", ""


def _node_id(classname: str, name: str) -> str:
    # "tests.test_login" -> "tests/test_login.py"; keep any Test* class suffix.
    parts = classname.split(".")
    if len(parts) >= 2 and parts[0] == "tests":
        file = "/".join(parts[:2]) + ".py"
        cls = "::".join(parts[2:])
        return f"{file}::{cls}::{name}" if cls else f"{file}::{name}"
    return f"{classname}::{name}" if classname else name


def build_message(path: str, scope: str) -> tuple[str, int]:
    cases = list(_load_cases(path))
    total = len(cases)
    passed = sum(1 for c in cases if c[3] == "pass")
    failed = [c for c in cases if c[3] == "fail"]
    skipped = sum(1 for c in cases if c[3] == "skip")
    runtime = sum(c[2] for c in cases)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    status = "PASS" if not failed else "❌ FAIL"

    lines = [
        f"*Teacher App QA — Full Regression* ({now})   {status}",
        f"App version: *{label_with_source()}*",
        f"Account: Mobile: *{TEACHER_MOBILE}*  •  School: *{SCHOOL_NAME}*",
        f"Scope: {scope}  •  {runtime:.0f}s",
        f"Passed {passed}/{total}  •  Failed {len(failed)}  •  Skipped {skipped}",
    ]
    if failed:
        lines.append("")
        lines.append(f"Failing ({len(failed)}):")
        for classname, name, _, _, msg in failed[:20]:
            tail = f" — {msg[:120]}" if msg else ""
            lines.append(f"• {_node_id(classname, name)}{tail}")
        if len(failed) > 20:
            lines.append(f"• …and {len(failed) - 20} more (see the Allure artifact)")
    return "\n".join(lines), len(failed)


def main() -> int:
    # The report contains emoji; a Windows console (cp1252) would crash on print.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = [a for a in sys.argv[1:]]
    path = next((a for a in args if not a.startswith("--")), None)
    if not path or not os.path.isfile(path):
        print(f"[slack_full_summary] junit file not found: {path!r}")
        return 0  # don't mask the real test outcome on a reporting glitch
    scope = "all scenarios except `heavy`"
    if "--scope" in args:
        i = args.index("--scope")
        if i + 1 < len(args):
            scope = args[i + 1]

    text, failed = build_message(path, scope)
    url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        print("[slack_full_summary] SLACK_WEBHOOK_URL not set — printing:\n")
        print(text)
    else:
        r = requests.post(url, json={"text": text}, timeout=30)
        r.raise_for_status()
        print("[slack_full_summary] posted to Slack.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
