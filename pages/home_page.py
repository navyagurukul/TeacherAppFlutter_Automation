"""Home / TeacherShell page object: header, bottom nav, and end drawer.

The shell keeps all five destinations mounted (IndexedStack) and swaps the
visible one; the header title changes per tab. The end drawer (hamburger) holds
Profile / Star Arena / Test / Zoom Training / Logout.
"""
from __future__ import annotations

from appium.webdriver.common.appiumby import AppiumBy

from data.test_data import Text
from pages.base_page import BasePage

# Bottom-nav label -> the header title shown once that tab is active.
NAV_TO_TITLE = {
    Text.NAV_HOME: Text.HOME_TITLE,
    Text.NAV_LESSONS: Text.TITLE_LESSON_PLAN,
    Text.NAV_CLASS: Text.TITLE_CLASS_REPORT,
    Text.NAV_STUDENTS: Text.TITLE_STUDENT_REPORT,
    Text.NAV_MANAGE: Text.TITLE_MANAGEMENT,
}

# Home-dashboard box -> the header title shown after tapping it.
BOX_TO_TITLE = {
    Text.BOX_LESSON_PLAN: Text.TITLE_LESSON_PLAN,
    Text.BOX_CLASS_REPORT: Text.TITLE_CLASS_REPORT,
    Text.BOX_STUDENT_REPORT: Text.TITLE_STUDENT_REPORT,
    Text.BOX_MANAGEMENT: Text.TITLE_MANAGEMENT,
}


class HomePage(BasePage):
    def wait_loaded(self, timeout: int = 30):
        # Header shows "Welcome!" on the default Home tab after login.
        self.wait_visible(Text.HOME_TITLE, timeout=timeout)
        return self

    def is_loaded(self) -> bool:
        return self.is_visible(Text.HOME_TITLE, timeout=10)

    def is_loaded_soon(self, timeout: int = 12) -> bool:
        """Non-fatal check used to branch login-vs-register: did we land on the
        home dashboard within `timeout` seconds?"""
        return self.is_visible(Text.HOME_TITLE, timeout=timeout)

    # -- bottom navigation ----------------------------------------------------

    def go_to(self, nav_label: str):
        self.tap_text(nav_label)
        expected = NAV_TO_TITLE[nav_label]
        self.wait_visible(expected, timeout=20)
        return self

    def current_title_is(self, title: str) -> bool:
        return self.is_visible(title, timeout=10)

    def go_home(self):
        self.tap_text(Text.NAV_HOME)
        self.wait_visible(Text.HOME_TITLE, timeout=20)
        return self

    # -- home dashboard boxes -------------------------------------------------

    def open_box(self, box_label: str):
        """Tap a home-dashboard box and wait for its section to load."""
        self.tap_desc(box_label)
        self.wait_visible(BOX_TO_TITLE[box_label], timeout=25)
        return self

    # -- end drawer -----------------------------------------------------------

    def open_menu(self):
        # The header hamburger is an IconButton with tooltip 'Menu', which Flutter
        # exposes as its semantics label (content-desc) — tap it directly.
        self.tap_desc("Menu")
        return self

    def open_profile(self):
        self.open_menu()
        self.tap_text(Text.MENU_PROFILE)
        return self

    def logout(self):
        self.open_menu()
        # Wait for the drawer to finish opening before tapping Logout.
        self.wait_visible(Text.MENU_LOGOUT, timeout=15)
        self.tap_text(Text.MENU_LOGOUT)
        return self
