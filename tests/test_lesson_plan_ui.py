"""UI sample checks for Lesson Plan: confirm the app actually opens a PDF in the
in-app viewer and launches the video player. Exhaustive URL validation is done
separately in test_lesson_plan_links.py; here we prove the viewers launch.

The specific plan/PDF/video to drive are discovered from the API so the test
stays valid as content changes.
"""
import time

import pytest

from data.test_data import TEACHER_MOBILE, Text
from pages.lesson_plan_page import LessonPlanPage
from pages.login_page import LoginPage
from utils.eg_api import EgApi, best_video_urls


@pytest.fixture(scope="session")
def lesson_targets():
    """Find, in the first class, a plan with a PDF and a plan with a video."""
    api = EgApi()
    api.login(TEACHER_MOBILE)
    classes = api.classes(api.school_id())
    assert classes, "no classes"
    cls = classes[0]
    class_name = cls.get("class_name") or cls.get("name")

    pdf_target = None
    video_target = None
    for p in api.plans(cls.get("id"))[:6]:
        detail = api.plan_detail(p.get("id"))
        title = p.get("display_name") or p.get("name")
        if pdf_target is None:
            for pdf in detail.get("pdfs", []) or []:
                if pdf.get("pdf_url") and pdf.get("title"):
                    pdf_target = (title, pdf["title"])
                    break
        if video_target is None:
            for v in detail.get("videos", []) or []:
                if best_video_urls(v) and v.get("display_name"):
                    video_target = (title, v["display_name"])
                    break
        if pdf_target and video_target:
            break
    return {"class_name": class_name, "pdf": pdf_target, "video": video_target}


@pytest.mark.lessons
def test_lesson_pdf_opens_in_viewer(driver, lesson_targets):
    if not lesson_targets["pdf"]:
        pytest.skip("no PDF material found in the first class")
    plan_title, pdf_title = lesson_targets["pdf"]

    home = LoginPage(driver).login_or_register(TEACHER_MOBILE)
    home.go_to(Text.NAV_LESSONS)

    lp = LessonPlanPage(driver)
    assert lp.is_loaded()
    lp.expand_plan(plan_title)
    lp.open_pdf(pdf_title)

    assert not lp.pdf_failed(), f"PDF '{pdf_title}' opened but failed to load"
    assert lp.pdf_viewer_opened(), f"PDF viewer did not open for '{pdf_title}'"


@pytest.mark.lessons
def test_lesson_video_plays_seeks_and_all_languages(driver, lesson_targets):
    """Open the video, confirm it plays, exercise the transport (fast-forward,
    or rewind if forward doesn't take), then switch through EVERY language chip
    and confirm each one plays. We never sit through a whole clip."""
    if not lesson_targets["video"]:
        pytest.skip("no video material found in the first class")
    plan_title, video_name = lesson_targets["video"]

    home = LoginPage(driver).login_or_register(TEACHER_MOBILE)
    home.go_to(Text.NAV_LESSONS)

    lp = LessonPlanPage(driver)
    assert lp.is_loaded()
    lp.expand_plan(plan_title)
    lp.open_video(video_name)

    assert not lp.video_failed(), f"Video '{video_name}' opened but failed to play"
    assert lp.video_player_opened(video_name), (
        f"Video player did not open for '{video_name}'"
    )

    # Confirm playback started.
    start = lp.video_position_seconds()
    assert start is not None, "video position/duration not shown — did it start?"

    # Fast-forward; if it doesn't take, rewind instead. Either proves the
    # transport controls seek the playback position.
    lp.fast_forward()
    time.sleep(1)
    after_ff = lp.video_position_seconds()
    seeked = after_ff is not None and after_ff >= start + 3
    if not seeked:
        lp.rewind()
        lp.rewind()
        time.sleep(1)
        after_rw = lp.video_position_seconds()
        seeked = (
            after_rw is not None and after_ff is not None and after_rw < after_ff
        )
    assert seeked, "neither fast-forward nor rewind moved the playback position"

    # Play the video in every offered language.
    languages = lp.available_languages()
    assert languages, "no language chips were shown for this video"
    results = {}
    for lang in languages:
        lp.select_language(lang)
        results[lang] = lp.wait_playing(timeout=30)
    failed = [lang for lang, ok in results.items() if not ok]
    assert not failed, (
        f"languages that failed to play: {failed} (checked {languages})"
    )
