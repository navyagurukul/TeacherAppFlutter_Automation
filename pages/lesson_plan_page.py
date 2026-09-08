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

from data.test_data import Text
from pages.base_page import BasePage

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
        self.scroll_to_desc(current_label)
        self.tap_desc(current_label)
        try:
            self.tap_desc(class_name, timeout=4)
        except Exception:
            self.scroll_to_desc(class_name)
            self.tap_desc(class_name)
        self.wait_visible(class_name, timeout=15)
        return self

    def collapse_plan(self, plan_title: str):
        # Tapping an expanded card's header collapses it again.
        self.scroll_to_desc_contains(plan_title)
        self.tap_desc_contains(plan_title)
        return self

    def go_back(self):
        self.driver.back()
        return self

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
