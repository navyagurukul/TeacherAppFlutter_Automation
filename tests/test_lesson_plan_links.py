"""Data-level Lesson Plan audit (no UI): for every class and every topic, verify
each PDF loads, each video MP4 loads, and every link embedded inside the PDFs
loads. A full markdown report lands in reports/lesson_plan_links.md.

Marked `heavy`, so the marker-driven device suites (tiered-suite, nightly,
android-ui -- all `-m "not heavy"`) skip it: the crawl runs 30+ minutes serially
and would hold the Pixel that whole time for a check that needs no device. The
audit still runs in full every morning via daily-report.yml, which invokes
`run_daily.py --audit-only` -> pytest on this file by path, with no `-m` filter.

Scope can be trimmed for a quick run:
    LESSON_CLASS_LIMIT=1 LESSON_PLAN_LIMIT=2 pytest tests/test_lesson_plan_links.py
"""
import os

import pytest

from config import settings
from data.test_data import TEACHER_MOBILE
from utils import lesson_audit


def _int_env(name):
    v = os.getenv(name)
    return int(v) if v and v.isdigit() else None


@pytest.fixture(scope="session")
def audit():
    """Crawl + validate the whole lesson-plan catalogue once, share across tests."""
    report = lesson_audit.run_audit(
        mobile=TEACHER_MOBILE,
        base_url=os.getenv("LESSON_BASE_URL") or "",
        class_limit=_int_env("LESSON_CLASS_LIMIT"),  # type: ignore[arg-type]
        plan_limit=_int_env("LESSON_PLAN_LIMIT"),  # type: ignore[arg-type]
    )
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lesson_audit.write_markdown(report, settings.REPORTS_DIR / "lesson_plan_links.md")
    return report


def _summarize(broken):
    lines = [f"{len(broken)} broken:"]
    lines.extend(
        f"  [{i.cls} / {i.topic}] {i.label} -> {i.status} {i.note} {i.url[:70]}"
        for i in broken[:25]
    )
    if len(broken) > 25:
        lines.append(f"  ... and {len(broken) - 25} more (see reports/lesson_plan_links.md)")
    return "\n".join(lines)


@pytest.mark.lessons
@pytest.mark.heavy
def test_catalogue_not_empty(audit):
    assert audit.classes > 0, "No classes returned"
    assert audit.of_kind("pdf") or audit.of_kind("video"), "No PDFs or videos found at all"


@pytest.mark.lessons
@pytest.mark.heavy
def test_all_pdfs_load(audit):
    broken = audit.broken("pdf")
    assert not broken, "PDFs that did not load:\n" + _summarize(broken)


@pytest.mark.lessons
@pytest.mark.heavy
def test_all_videos_load(audit):
    broken = audit.broken("video")
    assert not broken, "Videos that did not load:\n" + _summarize(broken)


@pytest.mark.lessons
@pytest.mark.heavy
def test_all_in_pdf_links_load(audit):
    broken = audit.broken("pdf-link")
    assert not broken, "Links inside PDFs that did not load:\n" + _summarize(broken)
