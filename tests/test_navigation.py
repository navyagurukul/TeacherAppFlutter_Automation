"""Bottom-nav smoke: log in once, then visit each destination and assert its
header title. Uses the Sanskruthi school."""
import pytest

from data.test_data import TEACHER_MOBILE, Text
from pages.home_page import NAV_TO_TITLE
from pages.login_page import LoginPage
from utils import school_enrolment


@pytest.mark.smoke
@pytest.mark.navigation
@pytest.mark.parametrize(
    "nav_label",
    [Text.NAV_LESSONS, Text.NAV_CLASS, Text.NAV_STUDENTS, Text.NAV_MANAGE, Text.NAV_HOME],
)
def test_bottom_nav_opens_each_tab(driver, nav_label):
    home = LoginPage(driver).login_or_register(TEACHER_MOBILE)
    home.go_to(nav_label)
    assert home.current_title_is(NAV_TO_TITLE[nav_label]), (
        f"Tab '{nav_label}' did not show title '{NAV_TO_TITLE[nav_label]}'"
    )


@pytest.mark.smoke
@pytest.mark.navigation
def test_home_shows_enrolment_counts(driver):
    # The home dashboard's school-summary card reads "Registered: <n>" and
    # "Remaining: <n>". Assert both are shown and record them so the daily
    # report can publish the seats still open (utils/school_enrolment.py).
    home = LoginPage(driver).login_or_register(TEACHER_MOBILE)
    counts = home.enrolment_counts()
    assert counts, "home dashboard did not show the Registered/Remaining counts"
    # The donut centre always carries the total (a "256 / of 348" node).
    # Requiring it keeps the cross-check below unconditional: when `total`
    # was allowed to be None the sum was never verified, and a mis-paired
    # legend published Remaining == Registered to Slack, suite still green.
    assert counts["total"] is not None, (
        f"could not read the total strength from the donut centre: {counts}"
    )
    assert counts["registered"] + counts["remaining"] == counts["total"], (
        f"counts do not add up to the total strength: {counts}"
    )
    school_enrolment.capture(counts)
