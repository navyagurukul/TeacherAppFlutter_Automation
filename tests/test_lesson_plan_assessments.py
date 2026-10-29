"""Lesson Plan assessments, for EVERY class: each card under a lesson plan shows
the button for its current state - START (not started), STOP (in progress) or
RESTART (stopped). Read-only: compares the app with the backend, which is what
the Student app reads, and never presses the buttons (that would open or close
the test for real students).
"""
import pytest

from data.test_data import TEACHER_MOBILE, Text
from pages.lesson_plan_page import LessonPlanPage
from pages.login_page import LoginPage
from utils.eg_api import EgApi

# Buttons the card may show for each backend status. A test the backend marks
# `completed` that the teacher has not stopped from the app still shows STOP, so
# the teacher can stop it; once stopped from the app it shows RESTART.
ACTIONS_FOR_STATUS = {
    "locked": {"START"},
    "unlocked": {"STOP"},
    "completed": {"STOP", "RESTART"},
}


@pytest.fixture(scope="module")
def class_assessments():
    """[(class name, [assessment, ...]), ...] for every class of the school."""
    api = EgApi()
    api.login(TEACHER_MOBILE)
    classes = api.classes(api.school_id())
    assert classes, "no classes"
    return [(c.get("class_name"), api.assessments(str(c["id"]))) for c in classes]


@pytest.mark.regression
@pytest.mark.lessons
@pytest.mark.tests_flow
def test_assessment_buttons_match_backend(driver, class_assessments, record_property):
    home = LoginPage(driver).login_or_register(TEACHER_MOBILE)
    home.go_to(Text.NAV_LESSONS)
    lp = LessonPlanPage(driver)
    assert lp.is_loaded()

    mismatches, checked = [], []
    for class_name, tests in class_assessments:
        if not tests:
            checked.append(f"{class_name}: no assessments")
            continue
        lp.ensure_class(class_name)
        cards = lp.assessment_actions(wanted=[t["display_name"] for t in tests])
        bad = 0
        for test in tests:
            name = test["display_name"]
            expected = ACTIONS_FOR_STATUS.get(str(test["status"]).lower(), set())
            shown = cards.get(name)
            if shown not in expected:
                bad += 1
                mismatches.append(
                    f"{class_name} / {name} (under {test['plan']!r}): backend "
                    f"{test['status']!r} expects {'/'.join(sorted(expected))}, "
                    f"app shows {shown or 'no card'}"
                )
        checked.append(f"{class_name}: {len(tests) - bad}/{len(tests)} cards match")
    print("\n[assessments] " + "\n[assessments] ".join(checked))
    record_property("assessments_by_class", " | ".join(checked))
    assert not mismatches, (
        f"{len(mismatches)} assessment card(s) do not match the backend:\n- "
        + "\n- ".join(mismatches)
    )
