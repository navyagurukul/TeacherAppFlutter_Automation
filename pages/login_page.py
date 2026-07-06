"""Login screen page object.

Flow: tap the School field -> a searchable bottom sheet opens -> search + tap the
school -> enter the 10-digit mobile -> tap LOG IN. On success the app replaces
the login screen with the TeacherShell (home).
"""
from __future__ import annotations

import re

from appium.webdriver.common.appiumby import AppiumBy

from data.test_data import (
    LICENSE_CODE,
    SCHOOL_NAME,
    SCHOOL_SEARCH,
    TEACHER_LANGUAGE,
    TEACHER_NAME,
    Text,
)
from pages.base_page import BasePage
from pages.home_page import HomePage
from pages.register_page import LicenseDialog, RegisterPage


class LoginPage(BasePage):
    def is_loaded(self) -> bool:
        return self.is_visible(Text.SIGN_IN_HEADING, timeout=20)

    def select_school(self, school_name: str = SCHOOL_NAME, search: str = SCHOOL_SEARCH):
        # Open the school picker (the field shows the "Select school" hint until
        # a school is chosen).
        self.tap_text(Text.SELECT_SCHOOL_HINT)
        # The picker is a modal bottom sheet with an autofocused search box.
        box = self.first_edit_field()
        self.type_into(box, search)
        # Tap the matching row by its semantics label (content-desc) so we don't
        # accidentally match the search field, which now holds the same prefix.
        self.tap_desc(school_name)
        self.hide_keyboard()
        return self

    def enter_mobile(self, mobile: str):
        field = self.first_edit_field()
        self.type_into(field, mobile)
        self.hide_keyboard()
        return self

    def tap_login(self):
        self.tap_text(Text.LOGIN_BUTTON)
        return self

    def tap_register(self):
        self.tap_text(Text.REGISTER_BUTTON)
        return self

    def login(self, school_name: str, mobile: str) -> HomePage:
        self.select_school(school_name)
        self.enter_mobile(mobile)
        self.tap_login()
        home = HomePage(self.driver)
        home.wait_loaded()
        return home

    def register(
        self,
        mobile: str,
        name: str = TEACHER_NAME,
        language: str = TEACHER_LANGUAGE,
        license_code: str = LICENSE_CODE,
    ) -> HomePage:
        """Full REGISTER path: license code -> name + language -> submit -> home.
        School selection isn't needed here; the license code resolves the school.
        """
        self.enter_mobile(mobile)
        self.tap_register()
        LicenseDialog(self.driver).enter_code_and_continue(license_code)
        reg = RegisterPage(self.driver)
        reg.wait_loaded()
        reg.enter_name(name)
        reg.select_language(language)
        reg.submit()
        home = HomePage(self.driver)
        home.wait_loaded()
        return home

    def login_or_register(
        self,
        mobile: str = None,
        name: str = TEACHER_NAME,
        language: str = TEACHER_LANGUAGE,
    ) -> HomePage:
        """Try to log in; if the number isn't registered, enroll it via the
        license code. Mirrors the real teacher onboarding: enter number -> LOG IN,
        and register only when needed."""
        from data.test_data import TEACHER_MOBILE

        mobile = mobile or TEACHER_MOBILE
        self.select_school()
        self.enter_mobile(mobile)
        self.tap_login()

        home = HomePage(self.driver)
        if home.is_loaded_soon(timeout=12):
            return home

        # Login didn't reach home (number not registered) -> register it. The
        # school is already selected and the mobile already entered.
        self.tap_register()
        LicenseDialog(self.driver).enter_code_and_continue(LICENSE_CODE)
        reg = RegisterPage(self.driver)
        reg.wait_loaded()
        reg.enter_name(name)
        reg.select_language(language)
        reg.submit()
        home.wait_loaded()
        return home

    # -- app version ----------------------------------------------------------

    def app_version_label(self) -> str | None:
        """The version footer shown at the bottom of the login screen, e.g.
        'ENGLISH GURUKUL TEACHER PORTAL V2.3.6' (rendered from PackageInfo). The
        daily report ties its summary to this exact string. Returns None if the
        footer isn't present (e.g. the version couldn't be read on-device)."""
        try:
            el = self.find_by_text("TEACHER PORTAL", exact=False, timeout=10)
        except Exception:
            return None
        base = (el.text or el.get_attribute("content-desc") or "").strip()
        # Flutter renders the version ("V2.3.6") as a separate text node from the
        # "TEACHER PORTAL" label, so `base` usually lacks it. Find that node and
        # stitch it on, so the captured label carries a real version number.
        if re.search(r"\d+\.\d+", base):
            return base or None
        version = self._find_version_text()
        if version:
            return f"{base} {version}".strip() if base else version
        return base or None

    def _find_version_text(self) -> str | None:
        """Locate the login-footer version node ('V2.3.6'). Best-effort: matches
        the first node whose text/content-desc contains a dotted version. Returns
        None on any failure so the caller can fall back gracefully."""
        for selector in (
            r'new UiSelector().textMatches(".*\d+\.\d+.*")',
            r'new UiSelector().descriptionMatches(".*\d+\.\d+.*")',
        ):
            try:
                el = self.driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, selector)
            except Exception:
                continue
            val = (el.text or el.get_attribute("content-desc") or "").strip()
            if val and re.search(r"\d+\.\d+", val):
                return val
        return None

    # -- validation helpers ---------------------------------------------------

    def validation_error_visible(self, message: str) -> bool:
        return self.is_visible(message, timeout=8)
