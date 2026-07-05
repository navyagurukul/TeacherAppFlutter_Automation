"""Exhaustive UI sweep: for EVERY class in the Lesson tab's class dropdown, open
EVERY lesson plan's PDFs and videos in the app and confirm each viewer/player
launches. This is the UI counterpart to the API link audit (which checks the
URLs load); here we prove the app actually surfaces and opens each one.

Heavy and slow — opt in explicitly. Trim scope for a quick check:
    UI_CLASS_LIMIT=1 UI_PLAN_LIMIT=2 pytest -m heavy

The plan/PDF/video names to drive are read from the API so the sweep matches the
real catalogue.
"""
import os

import pytest

from config import settings
from data.test_data import TEACHER_MOBILE, Text
from pages.lesson_plan_page import LessonPlanPage
from pages.login_page import LoginPage
from utils.eg_api import EgApi, best_video_urls


def _limit(name):
    v = os.getenv(name)
    return int(v) if v and v.isdigit() else None


@pytest.fixture(scope="session")
def catalog():
    """Every class -> its plans -> the PDF titles and video names to open."""
    api = EgApi()
    api.login(TEACHER_MOBILE)
    sid = api.school_id()
    out = []
    for c in api.classes(sid):
        cname = c.get("class_name") or c.get("name")
        plans = []
        for p in api.plans(c.get("id")):
            d = api.plan_detail(p.get("id"))
            plans.append({
                "title": p.get("display_name") or p.get("name"),
                "pdfs": [pdf["title"] for pdf in d.get("pdfs", []) or []
                         if pdf.get("pdf_url") and pdf.get("title")],
                "videos": [v["display_name"] for v in d.get("videos", []) or []
                           if best_video_urls(v) and v.get("display_name")],
            })
        out.append({"name": cname, "plans": plans})
    return out


def _write_report(opened, failures, classes_done):
    path = settings.REPORTS_DIR / "lesson_ui_open.md"
    lines = ["# Lesson Plan — UI open sweep", ""]
    lines.append(f"- Classes swept: **{classes_done}**")
    lines.append(f"- PDFs opened OK: **{opened['pdf']}**")
    lines.append(f"- Videos opened OK: **{opened['video']}**")
    lines.append(f"- Failures: **{len(failures)}**")
    lines.append("")
    if failures:
        lines.append("| Class | Plan | Resource | Reason |")
        lines.append("|---|---|---|---|")
        for cls, plan, res, why in failures:
            lines.append(f"| {cls} | {plan} | {res} | {why} |")
    else:
        lines.append("✅ Every PDF and video opened in the app.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.mark.lessons
@pytest.mark.heavy
def test_open_all_pdfs_and_videos_every_class(driver, catalog):
    class_limit = _limit("UI_CLASS_LIMIT")
    plan_limit = _limit("UI_PLAN_LIMIT")
    classes = catalog[:class_limit] if class_limit else catalog

    home = LoginPage(driver).login_or_register(TEACHER_MOBILE)
    home.go_to(Text.NAV_LESSONS)
    lp = LessonPlanPage(driver)
    assert lp.is_loaded()

    current = catalog[0]["name"]   # the app defaults to the first class
    opened = {"pdf": 0, "video": 0}
    failures = []
    swept = 0

    for cls in classes:
        if cls["name"] != current:
            try:
                lp.select_class(current, cls["name"])
                current = cls["name"]
            except Exception as e:
                failures.append((cls["name"], "-", "select-class", str(e)[:60]))
                continue
        swept += 1

        plans = cls["plans"][:plan_limit] if plan_limit else cls["plans"]
        for plan in plans:
            if not plan["pdfs"] and not plan["videos"]:
                continue
            try:
                lp.expand_plan(plan["title"])
            except Exception as e:
                failures.append((cls["name"], plan["title"], "expand", str(e)[:60]))
                continue

            for title in plan["pdfs"]:
                try:
                    lp.open_pdf(title)
                except Exception as e:
                    failures.append((cls["name"], plan["title"], f"pdf:{title}", str(e)[:60]))
                    continue
                if lp.pdf_viewer_opened() and not lp.pdf_failed():
                    opened["pdf"] += 1
                else:
                    failures.append((cls["name"], plan["title"], f"pdf:{title}", "viewer not open"))
                lp.go_back()

            for name in plan["videos"]:
                try:
                    lp.open_video(name)
                except Exception as e:
                    failures.append((cls["name"], plan["title"], f"video:{name}", str(e)[:60]))
                    continue
                if lp.video_player_opened(name) and not lp.is_visible(
                    Text.VIDEO_PLAY_ERROR, timeout=2
                ):
                    opened["video"] += 1
                else:
                    failures.append((cls["name"], plan["title"], f"video:{name}", "player not open"))
                lp.go_back()

            try:
                lp.collapse_plan(plan["title"])
            except Exception:
                pass

    _write_report(opened, failures, swept)
    assert not failures, (
        f"{len(failures)} resource(s) did not open (opened {opened}). "
        f"First few: {failures[:8]} — full list in reports/lesson_ui_open.md"
    )
