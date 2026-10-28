"""Lesson Plan assessment status for the Slack reports.

Each lesson plan can carry assessments the teacher drives from the Lesson Plan
screen: START opens one for the class's students in the Student app, STOP closes
it, RESTART reopens it. This reads every class's assessments for the suite's
school from the backend (the same data the app and Student app read) and renders:

  * a count of Not started / In progress / Stopped,
  * one line per assessment with its plan and student progress,
  * what was started or stopped since the previous report, from a snapshot kept
    outside the repo (the runner's checkout is wiped every run).

    python -m utils.assessment_report        # print the section
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from data.test_data import SCHOOL_NAME, TEACHER_MOBILE
from utils.eg_api import EgApi

LABEL = {"locked": "Not started", "unlocked": "In progress", "completed": "Stopped"}
ICON = {"locked": "⚪", "unlocked": "🟢", "completed": "🔴"}

SNAPSHOT = Path(os.getenv(
    "ASSESSMENT_SNAPSHOT",
    Path.home() / ".eg-qa" / "teacher_app_assessments.json",
))


def collect() -> list[dict]:
    """[{class, plan, name, status, completed, in_progress, total}] for the school."""
    api = EgApi()
    api.login(TEACHER_MOBILE, SCHOOL_NAME)
    rows = []
    for cls in api.classes(api.school_id()):
        for test in api.assessments(str(cls["id"])):
            summary = test.get("summary") or {}
            rows.append({
                "class": cls.get("class_name", ""),
                "plan": test.get("plan", ""),
                "name": test.get("display_name", ""),
                "status": str(test.get("status", "")).lower(),
                "completed": summary.get("completed", 0),
                "in_progress": summary.get("in_progress", 0),
                "total": summary.get("total_students", 0),
            })
    return rows


def _key(row: dict) -> str:
    return f"{row['class']} / {row['name']}"


def _load_snapshot() -> dict:
    try:
        return json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_snapshot(rows: list[dict]) -> None:
    try:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps({_key(r): r["status"] for r in rows}, indent=1),
                            encoding="utf-8")
    except OSError:
        pass


def changes(rows: list[dict], previous: dict) -> list[str]:
    """'Class 1 / Assessment 1: In progress → Stopped' for every status change."""
    out = []
    for row in rows:
        before = previous.get(_key(row))
        if before and before != row["status"]:
            verb = {"unlocked": "STARTED", "completed": "STOPPED"}.get(row["status"], "changed")
            out.append(f"{_key(row)} {verb}: {LABEL.get(before, before)} → "
                       f"{LABEL.get(row['status'], row['status'])}")
    return out


def section(save: bool = True) -> list[str]:
    """Slack lines for the report. Never raises: a backend hiccup must not stop
    the test report itself from posting."""
    try:
        rows = collect()
    except Exception as exc:
        return [f"*Assessments (Lesson Plan)*: could not read from the backend — "
                f"{type(exc).__name__}: {str(exc)[:120]}"]
    if not rows:
        return [f"*Assessments (Lesson Plan)*: none set up for {SCHOOL_NAME}"]

    counts = {s: sum(r["status"] == s for r in rows) for s in LABEL}
    lines = [
        f"*Assessments (Lesson Plan)* — {SCHOOL_NAME}",
        "  •  ".join(f"{ICON[s]} {LABEL[s]} {counts[s]}" for s in LABEL),
    ]
    previous = _load_snapshot()
    moved = changes(rows, previous)
    if moved:
        lines.append("Since last report:")
        lines += [f"• {m}" for m in moved]
    elif previous:
        lines.append("Since last report: no assessment started or stopped")
    # Started and stopped ones individually; not-started ones per class, so a
    # school with dozens of untouched assessments stays readable.
    for status in ("unlocked", "completed"):
        for row in (r for r in rows if r["status"] == status):
            lines.append(
                f"{ICON[status]} {row['class']} — {row['name']} (_{row['plan']}_): "
                f"*{LABEL[status]}* · {row['completed']}/{row['total']} done, "
                f"{row['in_progress']} taking"
            )
    waiting: dict[str, int] = {}
    for row in rows:
        if row["status"] not in ("unlocked", "completed"):
            waiting[row["class"]] = waiting.get(row["class"], 0) + 1
    if waiting:
        lines.append(f"{ICON['locked']} Not started: "
                     + ", ".join(f"{c} ({n})" for c, n in waiting.items()))
    if save:
        _save_snapshot(rows)
    return lines


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(section(save="--save" in sys.argv)))
