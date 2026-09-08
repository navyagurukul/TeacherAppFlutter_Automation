"""Home / TeacherShell page object: header, bottom nav, and end drawer.

The shell keeps all five destinations mounted (IndexedStack) and swaps the
visible one; the header title changes per tab. The end drawer (hamburger) holds
Profile / Star Arena / Test / Zoom Training / Logout.
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET

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

_INT = re.compile(r"^\d+$")


def _count_for(values: list[str], label: str) -> int | None:
    """The count belonging to `label` in the summary legend. Matches the label
    node exactly ("Remaining", "Remaining:") so 'Registered Mobile' on the
    profile screen can never be mistaken for the dashboard's 'Registered', and
    accepts either layout: one merged node, or a label node followed by its
    number."""
    pattern = re.compile(rf"^{re.escape(label)}\s*:?\s*(\d+)?$", re.IGNORECASE)
    for i, value in enumerate(values):
        m = pattern.match(value)
        if not m:
            continue
        if m.group(1):
            return int(m.group(1))
        for nxt in values[i + 1:i + 4]:
            if _INT.match(nxt):
                return int(nxt)
    return None


def _total_for(values: list[str]) -> int | None:
    """Total strength from the donut centre, which reads "of 120" under the
    registered count."""
    for value in values:
        m = re.match(r"^of\s+(\d+)$", value, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


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

    # -- school summary card --------------------------------------------------

    def enrolment_counts(self, timeout: int = 25) -> dict | None:
        """Registered / Remaining student counts from the home dashboard's
        school-summary card, e.g. `{"registered": 42, "remaining": 78,
        "total": 120}`. `total` is None when the donut centre isn't readable.

        The card is API-backed, so this waits for the legend to paint. Flutter
        renders each legend row as a label node and a separate count node, so
        the count is taken from the first numeric node after its label rather
        than parsed out of one string. Returns None if the card never painted.
        """
        deadline = time.monotonic() + timeout
        while True:
            values = self._visible_text_nodes()
            registered = _count_for(values, Text.LEGEND_REGISTERED)
            remaining = _count_for(values, Text.LEGEND_REMAINING)
            if registered is not None and remaining is not None:
                return {
                    "registered": registered,
                    "remaining": remaining,
                    "total": _total_for(values),
                }
            if time.monotonic() >= deadline:
                return None
            time.sleep(1)

    def _visible_text_nodes(self) -> list[str]:
        """Every non-empty text / content-desc in the current hierarchy, in
        document order. One page_source read beats a locator call per node, and
        document order is what pairs a legend label with its count."""
        try:
            root = ET.fromstring(self.driver.page_source.encode("utf-8"))
        except Exception:
            return []
        out = []
        for node in root.iter():
            value = (node.get("text") or node.get("content-desc") or "").strip()
            if value:
                out.append(value)
        return out
