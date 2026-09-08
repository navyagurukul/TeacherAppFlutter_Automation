"""Login flow tests. All logins use the Sanskruthi school."""
import pytest

from config import settings
from data.test_data import (
    INVALID_MOBILE_SHORT,
    SCHOOL_NAME,
    TEACHER_MOBILE,
    Text,
)
from pages.login_page import LoginPage


@pytest.mark.sanity
@pytest.mark.smoke
@pytest.mark.login
def test_login_screen_loads(driver):
    login = LoginPage(driver)
    assert login.is_loaded(), "Login screen did not show 'Sign in to continue'"
    assert login.is_visible(Text.LOGIN_BUTTON)
    assert login.is_visible(Text.REGISTER_BUTTON)


@pytest.mark.sanity
@pytest.mark.smoke
@pytest.mark.login
def test_login_shows_app_version(driver):
    # The login footer reads "ENGLISH GURUKUL TEACHER PORTAL V<version>". Assert
    # it's shown and record it so the daily report can tie its summary to the
    # exact build the login screen displayed (utils/app_version.py reads this).
    login = LoginPage(driver)
    assert login.is_loaded()
    label = login.app_version_label()
    assert label and "TEACHER PORTAL" in label, (
        f"login screen did not show the app-version footer (got: {label!r})"
    )
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (settings.REPORTS_DIR / "app_version.txt").write_text(label, encoding="utf-8")


@pytest.mark.sanity
@pytest.mark.smoke
@pytest.mark.login
def test_login_or_register_reaches_home(driver):
    # Enter the teacher number and LOG IN; if it isn't registered yet, enroll it
    # via the SANK48 license code. Either path must land on the home dashboard.
    login = LoginPage(driver)
    home = login.login_or_register(TEACHER_MOBILE)
    assert home.is_loaded(), "Home dashboard ('Welcome!') did not load after login"


@pytest.mark.regression
@pytest.mark.login
def test_login_requires_school(driver):
    login = LoginPage(driver)
    login.enter_mobile(TEACHER_MOBILE)
    login.tap_login()
    assert login.validation_error_visible(Text.SCHOOL_REQUIRED), (
        "Expected the 'Please select a school' message"
    )


@pytest.mark.regression
@pytest.mark.login
def test_login_requires_mobile(driver):
    login = LoginPage(driver)
    login.select_school(SCHOOL_NAME)
    login.tap_login()
    assert login.validation_error_visible(Text.MOBILE_REQUIRED), (
        "Expected the 'Mobile number is required' validation error"
    )


@pytest.mark.regression
@pytest.mark.login
def test_login_rejects_short_mobile(driver):
    login = LoginPage(driver)
    login.select_school(SCHOOL_NAME)
    login.enter_mobile(INVALID_MOBILE_SHORT)
    login.tap_login()
    assert login.validation_error_visible(Text.MOBILE_INVALID), (
        "Expected the 'Enter a valid 10-digit number' validation error"
    )
