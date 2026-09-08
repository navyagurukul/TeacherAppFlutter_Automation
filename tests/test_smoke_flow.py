"""End-to-end smoke journey for the teacher app (Sanskruthi School - Nalgonda):

login-or-register
    -> open each home-dashboard box (Lesson Plan, Class Report, Student Report,
    Management) and confirm the section loads
    -> open each bottom tab (Lessons, Class, Students, Manage) and confirm it loads
    -> open the drawer (3-bar menu) and Logout back to the login screen

"Loads with correct data" is asserted at smoke level as: the section's header
renders and the service-unreachable/error state is absent. Field-level data
assertions live in the per-area phase tests (see REGRESSION_PLAN.md).
"""
import pytest

from data.test_data import TEACHER_MOBILE, Text
from pages.home_page import HomePage
from pages.login_page import LoginPage


BOXES = [
    Text.BOX_LESSON_PLAN,
    Text.BOX_CLASS_REPORT,
    Text.BOX_STUDENT_REPORT,
    Text.BOX_MANAGEMENT,
]

TABS = [Text.NAV_LESSONS, Text.NAV_CLASS, Text.NAV_STUDENTS, Text.NAV_MANAGE]


@pytest.mark.smoke
@pytest.mark.navigation
def test_full_smoke_journey(driver):
    # 1) Login (registers via SANK48 the first time).
    home = LoginPage(driver).login_or_register(TEACHER_MOBILE)
    assert home.is_loaded(), "Home dashboard did not load after login"

    # 2) Home-dashboard boxes: open each, confirm its section loads, return home.
    # open_box() waits for the section header and raises if it never appears,
    # so reaching go_home() means the box navigated and its screen rendered.
    for box in BOXES:
        home.open_box(box)
        home.go_home()

    # 3) Bottom tabs: open each and confirm its header title.
    for tab in TABS:
        home.go_to(tab)
    home.go_to(Text.NAV_HOME)

    # 4) Drawer -> Logout -> back on the login screen.
    home.logout()
    login = LoginPage(driver)
    assert login.is_loaded(), "Logout did not return to the login screen"
