"""Base page object: Flutter-aware element helpers over the UiAutomator2 tree.

Flutter renders to a canvas, so widgets surface in Android's accessibility tree
mostly as their **text** or **content-desc** (semantics label). These helpers
therefore locate primarily by visible text, with a content-desc fallback, and
centralise the waits so page objects stay declarative.
"""
from __future__ import annotations

import time
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
