"""Run the Teacher App QA pass and post a per-area summary to Slack. Built for a
daily scheduled run.

The report is grouped by area — **Login, Tabs, Lesson Plans, PDFs, Videos** — each
with its own PASS/FAIL, and headed with the **app version shown on the login
screen** (e.g. V2.3.6) and the school's **Registered / Remaining** enrolment
counts as the home dashboard shows them. Overall PASS only when every area
passes.

Scope selection (no pytest args needed):
  * The device-free **Lesson-Plan media audit** (Lesson Plans / PDFs / Videos,
    validated against real data) always runs — reliable unattended, phone or not.
  * The **Login** and **Tabs** UI areas run too *when a device + Appium are up*.
    With no device they're reported as "skipped — no device", not failed.

Usage (with the venv python):
    python run_daily.py                 # auto scope -> Slack
    python run_daily.py --audit-only    # force device-free media audit only
    python run_daily.py --with-ui       # force-include the Login/Tabs UI areas
    python run_daily.py tests/test_x.py # run an explicit pytest scope instead

Config (.env or environment):
    SLACK_WEBHOOK_URL   Slack Incoming Webhook URL (required to post)
    DAILY_INCLUDE_UI    force the UI areas on ("1") or off ("0"); default = auto
    APPIUM_SERVER       used to probe whether Appium is up (default 127.0.0.1:4723)
"""
from __future__ import annotations

import datetime
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT))
from data.test_data import SCHOOL_NAME, TEACHER_MOBILE  # noqa: E402

# Windows consoles default to cp1252, which can't print the emoji in the report.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
if not os.path.exists(PY):
    PY = sys.executable
REPORTS = ROOT / "reports"

# Device-free media audit (Lesson Plans / PDFs / Videos, validated on real data).
AUDIT_FILES = ["tests/test_lesson_plan_links.py"]
# UI areas that need a device + Appium (Login, Tabs, and PDF/Video launch).
UI_FILES = [
    "tests/test_login.py",
    "tests/test_navigation.py",
    "tests/test_lesson_plan_ui.py",
]

# Report order. Every run shows all five so a missing area is visible, not silent.
AREAS = ["Login", "Tabs", "Lesson Plans", "PDFs", "Videos"]


def classify(classname: str, name: str) -> str:
    """Map a junit testcase to its report area."""
    c = (classname or "").replace(".", "/").lower()
    n = (name or "").lower()
    if "test_login" in c:
        return "Login"
    if "test_navigation" in c or "test_smoke_flow" in c:
        return "Tabs"
    # Lesson-plan tests split by what they exercise.
    if "in_pdf" in n or "in-pdf" in n or "catalogue" in n:
        return "Lesson Plans"
    if "pdf" in n:
        return "PDFs"
    if "video" in n:
        return "Videos"
    return "Lesson Plans"


# ---- running pytest ---------------------------------------------------------

def run_pytest(files, junit_name):
    REPORTS.mkdir(parents=True, exist_ok=True)
    junit = REPORTS / junit_name
    if junit.exists():
        junit.unlink()
    cmd = [PY, "-m", "pytest", *files, f"--junitxml={junit}", "-p", "no:cacheprovider"]
    subprocess.run(cmd, cwd=str(ROOT))
    return junit


def parse_junit(path):
    """Return per-testcase records: (area, name, ok)."""
    if not path or not path.exists():
        return []
    root = ET.parse(path).getroot()
    suites = root.findall("testsuite") or [root]
    out = []
    for s in suites:
        for tc in s.findall("testcase"):
            failed = tc.find("failure") is not None or tc.find("error") is not None
            skipped = tc.find("skipped") is not None
            area = classify(tc.get("classname"), tc.get("name"))
            out.append({
                "area": area,
                "name": tc.get("name"),
                "ok": not failed and not skipped,
                "failed": failed,
                "skipped": skipped,
                "time": float(tc.get("time", 0) or 0),
            })
    return out


# ---- device / appium probing ------------------------------------------------

def device_connected() -> bool:
    adb = shutil.which("adb")
    if not adb:
        return False
    try:
        out = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=15)
    except Exception:
        return False
    lines = [l for l in out.stdout.splitlines()[1:] if l.strip()]
    return any(l.split()[-1] == "device" for l in lines)


def appium_up() -> bool:
    base = os.getenv("APPIUM_SERVER", "http://127.0.0.1:4723").rstrip("/")
    try:
        with urllib.request.urlopen(base + "/status", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def want_ui() -> bool:
    """Decide whether to run the Login/Tabs UI areas."""
    flag = os.getenv("DAILY_INCLUDE_UI", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    if flag in {"0", "false", "no"}:
        return False
    return device_connected() and appium_up()  # auto


# ---- report building --------------------------------------------------------

def area_line(area, records, ui_skipped):
    recs = [r for r in records if r["area"] == area]
    if not recs:
        if area in ("Login", "Tabs") and ui_skipped:
            return f"• {area:<13} ⤼ skipped — no device"
        return f"• {area:<13} ⤼ not run"
    total = len(recs)
    passed = sum(1 for r in recs if r["ok"])
    failed = [r["name"] for r in recs if r["failed"]]
    icon = "✅" if not failed else "❌"
    line = f"• {area:<13} {icon} {passed}/{total}"
    if failed:
        line += "  — " + ", ".join(failed[:3])
        if len(failed) > 3:
            line += f" +{len(failed) - 3} more"
    return line


def mrkdwn(text: str) -> str:
    """Markdown bold (**x**) -> Slack bold (*x*). The audit writes a real
    markdown file; Slack's mrkdwn would print the doubled asterisks verbatim."""
    return text.replace("**", "*")


def audit_summary(since: float = 0.0):
    """Split the audit's bullets into (account lines, media line).

    The Mobile/School bullets identify *whose* catalogue was crawled, so they
    belong in the report header rather than buried in the media totals.
    `since` ignores a markdown file left by an earlier run, so a run that
    skipped the audit never reports yesterday's totals as today's."""
    p = REPORTS / "lesson_plan_links.md"
    if not p.exists() or p.stat().st_mtime < since:
        return [], None
    bullets = [ln[2:].strip() for ln in p.read_text(encoding="utf-8").splitlines()
               if ln.startswith("- ")]
    account = [mrkdwn(b) for b in bullets if b.startswith(("Mobile:", "School:"))]
    media = [mrkdwn(b) for b in bullets if not b.startswith(("Mobile:", "School:"))]
    return account, ("  •  ".join(media) if media else None)


def post_slack(text):
    url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        print("[run_daily] SLACK_WEBHOOK_URL not set — printing report instead:\n")
        print(text)
        return
    r = requests.post(url, json={"text": text}, timeout=30)
    r.raise_for_status()
    print("[run_daily] posted to Slack.")


# ---- main -------------------------------------------------------------------

def main():
    argv = sys.argv[1:]

    # Explicit pytest args -> run exactly those, still grouped by area.
    explicit = [a for a in argv if not a.startswith("--")]
    audit_only = "--audit-only" in argv
    force_ui = "--with-ui" in argv

    started = time.time()
    records = []
    ui_skipped = False

    # Forget the footer captured by an earlier run: after a release that stale
    # file would make today's report show the previous build's version.
    from utils.app_version import clear_capture
    clear_capture()
    from utils import school_enrolment
    school_enrolment.clear_capture()

    if explicit:
        records += parse_junit(run_pytest(explicit, "junit_explicit.xml"))
    else:
        # Always run the device-free media audit.
        records += parse_junit(run_pytest(AUDIT_FILES, "junit_audit.xml"))
        # Add the Login/Tabs UI areas when a device is available (or forced).
        run_ui = True if force_ui else (False if audit_only else want_ui())
        if run_ui:
            records += parse_junit(run_pytest(UI_FILES, "junit_ui.xml"))
        else:
            ui_skipped = True

    # Resolve the app version *after* the run so a UI login can have written the
    # live footer to reports/app_version.txt.
    from utils.app_version import label_with_source
    app_version = label_with_source()
    enrolment = school_enrolment.label_with_source()

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    account, media = audit_summary(since=started)

    if not records:
        post_slack(
            f"*Teacher App QA — Daily* ({now})   ⚠️ could not run any tests\n"
            f"App version: {app_version}"
        )
        sys.exit(1)

    total = len(records)
    passed = sum(1 for r in records if r["ok"])
    failed = sum(1 for r in records if r["failed"])
    skipped = sum(1 for r in records if r["skipped"])
    runtime = sum(r["time"] for r in records)
    status = "✅ PASS" if failed == 0 else "❌ FAIL"

    lines = [f"*Teacher App QA — Daily* ({now})   {status}"]
    lines.append(f"App version: *{app_version}*")
    if account:
        lines.append("Account: " + "  •  ".join(account))
    else:
        # No audit ran (or it failed before login) — still say who we'd use.
        lines.append(f"Account: Mobile: *{TEACHER_MOBILE}*  •  School: *{SCHOOL_NAME}*")
    lines.append(f"Enrolment: {enrolment}")
    lines += [
        f"Passed {passed}/{total}  •  Failed {failed}  •  Skipped {skipped}  •  {runtime:.0f}s",
        "",
    ]
    lines += [area_line(a, records, ui_skipped) for a in AREAS]

    if media:
        lines += ["", f"Lesson media (data): {media}"]

    post_slack("\n".join(lines))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
