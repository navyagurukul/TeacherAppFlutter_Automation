"""Base page object: Flutter-aware element helpers over the UiAutomator2 tree.

Flutter renders to a canvas, so widgets surface in Android's accessibility tree
mostly as their **text** or **content-desc** (semantics label). These helpers
therefore locate primarily by visible text, with a content-desc fallback, and
centralise the waits so page objects stay declarative.
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from typing import Optional

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEFAULT_TIMEOUT = 15


def _q(value: str) -> str:
    """Quote a string for XPath, handling embedded quotes via concat()."""
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    parts = value.split('"')
    return "concat(" + ', \'"\', '.join(f'"{p}"' for p in parts) + ")"


class BasePage:
    def __init__(self, driver):
        self.driver = driver

    # -- locator builders -----------------------------------------------------

    @staticmethod
    def _by_text_xpath(text: str, exact: bool = True) -> str:
        # Match either the visible text or the semantics label (content-desc),
        # which is how Flutter exposes most tappable widgets.
        if exact:
            return (
                f'//*[@text={_q(text)} or @content-desc={_q(text)}]'
            )
        return (
            f'//*[contains(@text,{_q(text)}) or contains(@content-desc,{_q(text)})]'
        )

    # -- waits / lookups ------------------------------------------------------

    def wait(self, timeout: int = DEFAULT_TIMEOUT) -> WebDriverWait:
        return WebDriverWait(self.driver, timeout)

    def find_by_text(self, text: str, exact: bool = True, timeout: int = DEFAULT_TIMEOUT):
        locator = (AppiumBy.XPATH, self._by_text_xpath(text, exact))
        return self.wait(timeout).until(EC.presence_of_element_located(locator))

    def wait_visible(self, text: str, exact: bool = True, timeout: int = DEFAULT_TIMEOUT):
        locator = (AppiumBy.XPATH, self._by_text_xpath(text, exact))
        return self.wait(timeout).until(EC.visibility_of_element_located(locator))

    def is_visible(self, text: str, exact: bool = True, timeout: int = 5) -> bool:
        try:
            self.wait_visible(text, exact=exact, timeout=timeout)
            return True
        except (TimeoutException, NoSuchElementException):
            return False

    # -- actions --------------------------------------------------------------

    def _click(self, locator, timeout: int):
        """Wait for a clickable element and click it, retrying on staleness —
        elements can be re-created mid-animation (drawers, dialogs, dropdowns)."""
        end = time.monotonic() + timeout
        last_exc = None
        while time.monotonic() < end:
            remaining = max(1, int(end - time.monotonic()))
            try:
                el = self.wait(remaining).until(EC.element_to_be_clickable(locator))
                el.click()
                return el
            except StaleElementReferenceException as exc:
                last_exc = exc
        if last_exc:
            raise last_exc
        raise TimeoutException(f"element not clickable: {locator}")

    def tap_text(self, text: str, exact: bool = True, timeout: int = DEFAULT_TIMEOUT):
        return self._click((AppiumBy.XPATH, self._by_text_xpath(text, exact)), timeout)

    def tap_desc(self, desc: str, timeout: int = DEFAULT_TIMEOUT):
        """Tap by exact semantics label (content-desc). Use this when a plain
        text match would be ambiguous — e.g. a list row whose label also equals
        the text a nearby search field currently holds."""
        return self._click((AppiumBy.ACCESSIBILITY_ID, desc), timeout)

    def tap_desc_contains(self, text: str, timeout: int = DEFAULT_TIMEOUT):
        """Tap the first node whose content-desc CONTAINS text. Needed for
        Flutter nodes that merge several labels into one semantics string (e.g. a
        lesson-plan card exposes 'Title\\n<pdfs>\\n<videos>')."""
        return self._click(
            (AppiumBy.XPATH, f"//*[contains(@content-desc, {_q(text)})]"), timeout
        )

    @staticmethod
    def _desc_first_line_xpath(label: str) -> str:
        # Flutter merges a row's texts into one content-desc joined by newlines,
        # e.g. "Class 1\nSPARKLE 1 / LEVEL 1 - EDITION 4". Match the exact label
        # alone or as the first line (starts-with on label + newline).
        return (f"//*[@content-desc={_q(label)} or "
                f"starts-with(@content-desc, {_q(label + chr(10))})]")

    def tap_desc_first_line(self, label: str, timeout: int = DEFAULT_TIMEOUT):
        """Tap a node whose content-desc is `label` or starts with `label` + a
        newline — for list rows that carry a trailing badge."""
        return self._click((AppiumBy.XPATH, self._desc_first_line_xpath(label)), timeout)

    # -- inline dropdowns -----------------------------------------------------
    # A class/test dropdown opens in place as its own small scroll list, so
    # UiScrollable (which scrolls the page) can't reach options outside it.

    def pick_dropdown_option(self, option: str, header: str | None = None) -> bool:
        """With a dropdown open, tap the row whose first line is `option`,
        scrolling inside the list down and then up. `header` is the label the
        closed dropdown shows; an exact match on it is the header, not a row."""
        xpath = self._desc_first_line_xpath(option)
        for direction, steps in (("down", 10), ("up", 20)):
            for _ in range(steps):
                hits = [e for e in self.driver.find_elements(AppiumBy.XPATH, xpath)
                        if option != header
                        or "\n" in (e.get_attribute("content-desc") or "")]
                if hits:
                    hits[-1].click()
                    return True
                if not self._scroll_dropdown(direction, exclude=header):
                    break
        return False

    def _dropdown_area(self, exclude: str | None = None):
        """(left, top, right, bottom) of the open dropdown's list. Its rows are
        labelled 'Name\\nBADGE' (or plain 'Class ...' without a badge), but so
        are lesson-plan cards ('Title\\n<pdfs>\\n<videos>') further down the page,
        so take the topmost row and the scrollable that tightly holds it - or,
        without one, the run of rows directly touching it."""
        rows, scrollables = [], []
        for e in ET.fromstring(self.driver.page_source).iter():
            m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", e.get("bounds") or "")
            if not m:
                continue
            box = tuple(int(g) for g in m.groups())
            if e.get("scrollable") == "true":
                scrollables.append(box)
            desc = e.get("content-desc") or ""
            if desc and desc != exclude:
                rows.append((desc, box))
        options = sorted((b for d, b in rows if "\n" in d), key=lambda b: b[1]) or \
            sorted((b for d, b in rows if d.startswith("Class ")), key=lambda b: b[1])
        if not options:
            return None
        # The list's rows touch each other; a "report ready" banner above it or
        # cards below it stand apart. So take the longest run of touching rows.
        runs = [[options[0]]]
        for box in options[1:]:
            if abs(box[1] - runs[-1][-1][3]) <= 5 and box[0] == runs[-1][-1][0]:
                runs[-1].append(box)
            else:
                runs.append([box])
        run = max(runs, key=len)
        first = run[0]
        cx, cy = (first[0] + first[2]) / 2, (first[1] + first[3]) / 2
        area = (min(b[0] for b in run), run[0][1], max(b[2] for b in run), run[-1][3])
        # The list's own scrollable is about as tall as its visible rows; the
        # page's scrollable also holds them but is far taller - skip that one.
        holding = [s for s in scrollables if s[0] <= cx <= s[2] and s[1] <= cy <= s[3]
                   and (s[3] - s[1]) <= (area[3] - area[1]) + 120]
        return min(holding, key=lambda s: (s[2] - s[0]) * (s[3] - s[1])) if holding else area

    def _visible_rows(self) -> list[str]:
        return [e.get("content-desc") for e in ET.fromstring(self.driver.page_source).iter()
                if "\n" in (e.get("content-desc") or "")
                or (e.get("content-desc") or "").startswith("Class ")]

    def _scroll_dropdown(self, direction: str = "down", exclude: str | None = None) -> bool:
        """Swipe the open dropdown's list one page; False once it no longer
        moves. (`mobile: scrollGesture` doesn't move these Flutter lists, so
        this is a plain touch swipe inside the list's bounds.)"""
        area = self._dropdown_area(exclude)
        if not area:
            return False
        left, top, right, bottom = area
        x, near_top, near_bottom = (left + right) // 2, top + 30, max(top + 31, bottom - 30)
        before = self._visible_rows()
        if direction == "down":
            self.driver.swipe(x, near_bottom, x, near_top, 600)
        else:
            self.driver.swipe(x, near_top, x, near_bottom, 600)
        time.sleep(0.8)
        return self._visible_rows() != before

    def scroll_to_desc_contains(self, text: str) -> Optional[object]:
        try:
            return self.driver.find_element(
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiScrollable(new UiSelector().scrollable(true))'
                f'.scrollIntoView(new UiSelector().descriptionContains("{text}"))',
            )
        except NoSuchElementException:
            return None

    def find_all_desc(self, desc: str, timeout: int = DEFAULT_TIMEOUT):
        locator = (AppiumBy.ACCESSIBILITY_ID, desc)
        self.wait(timeout).until(EC.presence_of_element_located(locator))
        return self.driver.find_elements(*locator)

    def tap_desc_nth(self, desc: str, index: int = -1, timeout: int = DEFAULT_TIMEOUT):
        """Tap the Nth element sharing a content-desc (default: the last). Useful
        when a lesson-plan header and its PDF row carry the same label."""
        els = self.find_all_desc(desc, timeout)
        els[index].click()
        return els[index]

    def first_edit_field(self, timeout: int = DEFAULT_TIMEOUT):
        locator = (AppiumBy.CLASS_NAME, "android.widget.EditText")
        return self.wait(timeout).until(EC.presence_of_element_located(locator))

    def type_into(self, element, value: str):
        element.click()
        element.clear()
        element.send_keys(value)

    def hide_keyboard(self):
        try:
            if self.driver.is_keyboard_shown():
                self.driver.hide_keyboard()
        except Exception:
            pass

    # -- scrolling ------------------------------------------------------------

    def scroll_to_desc(self, desc: str) -> Optional[object]:
        """Scroll a scrollable until the content-desc is on screen (UiScrollable)."""
        try:
            return self.driver.find_element(
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiScrollable(new UiSelector().scrollable(true))'
                f'.scrollIntoView(new UiSelector().description("{desc}"))',
            )
        except NoSuchElementException:
            return None

    def scroll_to_text(self, text: str, exact: bool = True) -> Optional[object]:
        """Fling/scroll a scrollable until the text is on screen (UiScrollable)."""
        match = "text" if exact else "textContains"
        try:
            return self.driver.find_element(
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiScrollable(new UiSelector().scrollable(true))'
                f'.scrollIntoView(new UiSelector().{match}({_q(text)}))',
            )
        except NoSuchElementException:
            return None
