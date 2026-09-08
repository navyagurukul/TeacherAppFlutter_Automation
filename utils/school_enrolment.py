"""Resolve the school's enrolment figures — the Registered / Remaining counts
the home dashboard shows on its school-summary card.

The daily report carries these so each Slack summary says how many student seats
the QA school has taken and how many are still open. Resolution order (first hit
wins), most-faithful first:

1. `reports/school_enrolment.txt` — the counts read live off the home dashboard
   during this run (written by tests/test_navigation.py). This is literally what
   the home screen displayed.
2. The API: `management/v1/schools/<id>/` -> `total_registered_students` and
   `total_strength`, the same payload the card is built from. Used when the UI
   areas were skipped (no device), so the figures still land in the report.

`remaining` is derived exactly as the app derives it — `total_strength -
total_registered_students`, floored at zero (see lib/models/school_summary.dart).
"""
from __future__ import annotations

import json

from config import settings

CAPTURED = settings.REPORTS_DIR / "school_enrolment.txt"


def capture(counts: dict) -> None:
    """Record what the home dashboard showed, for the report to read later."""
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    CAPTURED.write_text(json.dumps(counts), encoding="utf-8")


def clear_capture() -> None:
    """Drop a previous run's counts so today's report can't publish yesterday's
    numbers as today's."""
    try:
        CAPTURED.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _from_captured():
    if not CAPTURED.exists():
        return None
    try:
        counts = json.loads(CAPTURED.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(counts, dict):
        return None
    if counts.get("registered") is None or counts.get("remaining") is None:
        return None
    return counts


def _from_api():
    from data.test_data import TEACHER_MOBILE
    from utils.eg_api import EgApi

    api = EgApi()
    api.login(TEACHER_MOBILE)
    summary = api.school_summary(api.school_id())
    if not summary:
        return None

    def to_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    registered = to_int(summary.get("total_registered_students"))
    total = to_int(summary.get("total_strength"))
    if registered is None or total is None:
        return None
    return {"registered": registered, "remaining": max(total - registered, 0), "total": total}


SOURCES = [
    (_from_captured, "home screen"),
    (_from_api, "API"),
]


def resolve_with_source() -> tuple[dict | None, str]:
    """(counts, where they came from) so the report never claims the home screen
    showed figures it actually pulled from the API."""
    for source, origin in SOURCES:
        try:
            counts = source()
        except Exception:
            counts = None
        if counts:
            return counts, origin
    return None, "not found"


def resolve() -> dict | None:
    return resolve_with_source()[0]


def label_with_source() -> str:
    """e.g. 'Registered *42*  •  Remaining *78*  •  of *120*  (home screen)'."""
    counts, origin = resolve_with_source()
    if not counts:
        return f"unknown  ({origin})"
    parts = [
        f"Registered *{counts['registered']}*",
        f"Remaining *{counts['remaining']}*",
    ]
    if counts.get("total") is not None:
        parts.append(f"of *{counts['total']}*")
    return "  •  ".join(parts) + f"  ({origin})"
