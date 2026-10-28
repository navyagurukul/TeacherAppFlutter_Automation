"""Lesson Plan screen page object.

Layout: a class dropdown at the top, then a card per lesson plan. Expanding a
card reveals a "LESSON PDF" section (tappable PDF rows -> PdfViewerScreen) and a
"VIDEOS" section (tappable rows -> VideoPlayerScreen).

A plan's title and its PDF's title are sometimes identical, so PDF/video rows are
tapped as the *last* element sharing that label (the header is the first).
"""
from __future__ import annotations

import re
import time

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC

from data.test_data import Text
from pages.base_page import BasePage, _q

# "00:06 / 03:45" — chewie's position / duration label.
_POS_RE = re.compile(r'(\d+):(\d+)\s*/\s*\d+:\d+')

# Language chip labels a lesson video may offer (from lib/models/language.dart).
KNOWN_LANGUAGES = [
    "English", "Hindi", "Telugu", "Kannada", "Gujarati", "Marathi", "Tamil",
    "Malayalam", "Bengali", "Punjabi", "Odia", "Urdu", "Assamese", "Sanskrit",
]


class LessonPlanPage(BasePage):
    def is_loaded(self) -> bool:
        return self.is_visible(Text.TITLE_LESSON_PLAN, timeout=20)

    def open_class_dropdown(self, current_label: str):
        # The dropdown header shows the currently selected class name.
        self.tap_desc(current_label)
        return self

    def select_class(self, current_label: str, class_name: str):
        # Open via the header (which shows the current class), then pick the
        # target — scrolling the option list if it's long.
        # Since v2.5 each option also shows its program badge, merged into the
        # row's content-desc ("Class 1\nSPARKLE 1 / LEVEL 1 - EDITION 4"), so
        # match the class name as the first line rather than the whole label.
        self.scroll_to_desc(current_label)
        self.tap_desc(current_label)
        time.sleep(1.5)
        assert self.pick_dropdown_option(class_name, header=current_label), (
            f"class {class_name!r} not found in the dropdown under {current_label!r}")
        self.wait_visible(class_name, timeout=15)
        return self

    def scroll_to_top(self):
        try:
            self.driver.find_element(
                AppiumBy.ANDROID_UIAUTOMATOR,
                "new UiScrollable(new UiSelector().scrollable(true)).flingToBeginning(10)",
            )
        except Exception:
            pass  # the call reports "not found" after flinging; the scroll still happened
        return self

    def current_class(self) -> str | None:
        """The class the dropdown header shows (e.g. 'Class 4'). The screen opens
        on the teacher's last/assigned class, not necessarily the school's first."""
        for el in self.driver.find_elements(
            AppiumBy.XPATH, "//*[starts-with(@content-desc, 'Class ')]"
        ):
            desc = (el.get_attribute("content-desc") or "").strip()
            # "Class 4", "Class 1 - E2", "Class Level 3 - E4"; not the bare "Class" tab.
            if re.fullmatch(r"Class \S.*", desc) and "\n" not in desc:
                return desc
        return None

    def ensure_class(self, class_name: str):
        """Switch the dropdown to `class_name` unless it already shows it."""
        self.scroll_to_top()  # the dropdown header sits above the plan list
        current = self.current_class()
        if current and current != class_name:
            self.select_class(current, class_name)
        return self

    def collapse_plan(self, plan_title: str):
        # Tapping an expanded card's header collapses it again.
        self.scroll_to_desc_contains(plan_title)
        self.tap_desc_contains(plan_title)
        return self

    def go_back(self):
        self.driver.back()
        return self

    # -- assessments ----------------------------------------------------------
    # An assessment card sits under its lesson plan: a View whose content-desc
    # is its name ("Assessment 1") with one Button child labelled by its state -
    # START (not started), STOP (in progress) or RESTART (stopped).

    ASSESSMENT_ACTIONS = ("START", "STOP", "RESTART")

    def assessment_action(self, name: str, timeout: int = 15) -> str | None:
        """The button the named assessment card offers, scrolling it into view;
        None if the card is not in the list (searched down, then from the top)."""
        # A long plan list (29 plans) can still be loading or settling after a
        # class switch, so search down, then from the top, then once more after
        # a pause before calling the card missing.
        found = self.scroll_to_desc(name)
        for _ in range(2):
            if found is not None:
                break
            self.scroll_to_top()
            time.sleep(2)
            found = self.scroll_to_desc(name)
        if found is None:
            return None
        xpath = (f"//*[@content-desc={_q(name)}]/*[@content-desc='START' or "
                 f"@content-desc='STOP' or @content-desc='RESTART']")
        # scrollIntoView stops as soon as the card's top edge shows; a card at the
        # bottom of the screen has its button still off-screen and missing from
        # the tree. Nudge the list up until the button is in view.
        for attempt in range(4):
            try:
                el = self.wait(timeout if attempt == 3 else 3).until(
                    EC.presence_of_element_located((AppiumBy.XPATH, xpath))
                )
                return el.get_attribute("content-desc")
            except TimeoutException:
                self._nudge_up()
        return "card shown, no button" if self.find_all_desc_safe(name) else None

    def _nudge_up(self):
        size = self.driver.get_window_size()
        self.driver.execute_script("mobile: scrollGesture", {
            "left": 0, "top": int(size["height"] * 0.3), "width": size["width"],
            "height": int(size["height"] * 0.4), "direction": "down", "percent": 0.6,
        })

    def find_all_desc_safe(self, desc: str):
        return self.driver.find_elements(AppiumBy.ACCESSIBILITY_ID, desc)

    def expand_plan(self, plan_title: str):
        # A card's content-desc is "Title\n<pdfCount>\n<videoCount>", so match by
        # substring. Tapping the card toggles it open.
        self.scroll_to_desc_contains(plan_title)
        self.tap_desc_contains(plan_title)
        return self

    def open_pdf(self, pdf_title: str):
        # A PDF row's content-desc is exactly its title (the card carries the
        # counts too, so an exact match hits only the row).
        self.scroll_to_desc(pdf_title)
        self.tap_desc(pdf_title)
        return self

    def open_video(self, video_name: str):
        self.scroll_to_desc(video_name)
        self.tap_desc(video_name)
        return self

    # -- viewer assertions ----------------------------------------------------

    def pdf_viewer_opened(self) -> bool:
        # The page indicator is part of the merged app-bar title node, so match
        # on a substring rather than the whole label.
        return self.is_visible(Text.PDF_PAGE_INDICATOR, exact=False, timeout=20)

    def pdf_failed(self) -> bool:
        return self.is_visible(Text.PDF_OPEN_ERROR, timeout=3)

    def video_player_opened(self, video_name: str) -> bool:
        # On the pushed player screen the app-bar title shows, and the shell's
        # bottom nav ("Home") is gone.
        title = self.is_visible(video_name, timeout=20)
        left_shell = not self.is_visible(Text.NAV_HOME, timeout=2)
        return title and left_shell

    def video_failed(self) -> bool:
        return self.is_visible(Text.VIDEO_PLAY_ERROR, timeout=8)

    # -- video playback controls (chewie) -------------------------------------

    def _tap_video_surface(self):
        """Tap the video to TOGGLE the chewie control overlay."""
        size = self.driver.get_window_size()
        self.driver.tap([(size["width"] // 2, int(size["height"] * 0.35))])

    def _video_region(self):
        """Bounds of the video/overlay, taken from the position label ('MM:SS /
        MM:SS') which chewie stretches across the whole video area. None if the
        overlay isn't currently visible."""
        for e in self.driver.find_elements(
            AppiumBy.XPATH, '//*[contains(@content-desc, "/")]'
        ):
            if _POS_RE.search(e.get_attribute("content-desc") or ""):
                return e.rect
        return None

    def _reveal_controls(self, attempts: int = 5):
        """Show the overlay (if hidden) and return the video region. Chewie
        auto-hides controls and a tap toggles them, so we only tap when the
        overlay is absent."""
        for _ in range(attempts):
            region = self._video_region()
            if region:
                return region
            self._tap_video_surface()
            time.sleep(0.7)
        return None

    def video_position_seconds(self):
        """Current playback position in seconds (revealing the overlay if
        needed). None if the label never appears."""
        for _ in range(5):
            m = _POS_RE.search(self.driver.page_source)
            if m:
                return int(m.group(1)) * 60 + int(m.group(2))
            self._tap_video_surface()
            time.sleep(0.7)
        return None

    def _tap_transport(self, frac_x: float):
        """Tap a chewie transport button by position within the video region:
        the skip-back / play-pause / skip-forward row sits at the vertical
        centre; frac_x picks the column (~0.34 back, 0.5 pause, 0.66 forward)."""
        region = self._reveal_controls()
        assert region, "video controls did not appear"
        x = int(region["x"] + region["width"] * frac_x)
        y = int(region["y"] + region["height"] * 0.5)
        self.driver.tap([(x, y)])
        return self

    def fast_forward(self):
        return self._tap_transport(0.66)

    def rewind(self):
        return self._tap_transport(0.34)

    # -- language variants ----------------------------------------------------

    def available_languages(self):
        """Language chip labels currently offered below the player."""
        descs = set(re.findall(r'content-desc="([^"]*)"', self.driver.page_source))
        return [lang for lang in KNOWN_LANGUAGES if lang in descs]

    def select_language(self, language: str):
        self.tap_desc(language)
        return self

    def wait_playing(self, timeout: int = 30) -> bool:
        """True once the player is playing (position label present) — reloads a
        fresh controller when a language is switched. False if it errors out."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.is_visible(Text.VIDEO_PLAY_ERROR, timeout=1):
                return False
            if self.video_position_seconds() is not None:
                return True
            time.sleep(1)
        return False
