"""Bottom-nav smoke: log in once, then visit each destination and assert its
header title. Uses the Sanskruthi school."""
import pytest

from data.test_data import TEACHER_MOBILE, Text
from pages.home_page import NAV_TO_TITLE
from pages.login_page import LoginPage


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
