"""Class Report, Student Report, Star Arena and Test Report screens.

These screens lay their numbers out as tiles: a value node sits directly above
its caption node ("12.5%" over "AVG. ACCURACY"), as separate siblings in the
semantics tree. So values are read geometrically - the node right above a
caption, in the same column - from one page-source snapshot.
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from decimal import ROUND_HALF_UP, Decimal

from appium.webdriver.common.appiumby import AppiumBy

from pages.base_page import BasePage, _q

_BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


_PCT = re.compile(r"^(\d+(\.\d+)?%|-)$")


def pct(value) -> str:
    """How the app prints a percentage: one decimal + '%', or '-' when <= 0.
    Dart's toStringAsFixed rounds a half up (91.25 -> 91.3), unlike Python's
    format, which rounds it to even (91.2)."""
    try:
        v = Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return "-"
    return f"{v.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%" if v > 0 else "-"


class Node:
    def __init__(self, desc: str, bounds: str):
        self.desc = desc
        m = _BOUNDS.match(bounds or "")
        self.x1, self.y1, self.x2, self.y2 = (int(g) for g in m.groups()) if m else (0, 0, 0, 0)

    @property
    def cx(self):
        return (self.x1 + self.x2) / 2


class ReportsPage(BasePage):
    # -- reading -----------------------------------------------------------------

    def nodes(self) -> list[Node]:
        root = ET.fromstring(self.driver.page_source)
        return [Node(e.get("content-desc"), e.get("bounds"))
                for e in root.iter() if e.get("content-desc")]

    def value_above(self, caption: str, nodes: list[Node] | None = None,
                    below_y: int = 0) -> str | None:
        """Text of the node right above `caption` in the same column. With
        `below_y`, only captions under that y count (e.g. inside one card)."""
        nodes = nodes or self.nodes()
        caps = [n for n in nodes if n.desc == caption and n.y1 >= below_y]
        if not caps:
            return None
        cap = min(caps, key=lambda n: n.y1)
        above = [n for n in nodes if n.y2 <= cap.y1 + 2 and n.x1 <= cap.cx <= n.x2
                 and cap.y1 - n.y2 < 160 and n is not cap]
        if not above:
            return None
        return max(above, key=lambda n: n.y2).desc

    def tiles(self, captions, tries: int = 3) -> dict[str, str | None]:
        """Tile values by caption; re-read while a reload has them blank."""
        for _ in range(tries):
            nodes = self.nodes()
            got = {c: self.value_above(c, nodes) for c in captions}
            if all(v is not None for v in got.values()):
                return got
            self.settle(2)
        return got

    def wait_desc(self, desc: str, timeout: int = 30, exact: bool = True):
        xp = f"//*[@content-desc={_q(desc)}]" if exact else f"//*[contains(@content-desc,{_q(desc)})]"
        end = time.time() + timeout
        while time.time() < end:
            if self.driver.find_elements(AppiumBy.XPATH, xp):
                return True
            time.sleep(0.5)
        return False

    def settle(self, seconds: float = 2.5):
        """Let a filter/class switch finish its API call and repaint."""
        time.sleep(seconds)
        return self

    # -- dropdowns / pills ---------------------------------------------------------

    def choose(self, current_label: str, option: str):
        """Open the dropdown showing `current_label` and pick `option` (an option
        row may carry a trailing program badge, so match its first line)."""
        if current_label == option:
            return self
        for _ in range(2):
            self.tap_desc(current_label)
            time.sleep(1.5)
            if not self.pick_dropdown_option(option, header=current_label):
                raise AssertionError(
                    f"option {option!r} not found in the dropdown under {current_label!r}")
            self.settle()
            # A tap on a row half-hidden at the list's edge can close the list
            # without selecting it; confirm the header now shows the option.
            if self.driver.find_elements(AppiumBy.ACCESSIBILITY_ID, option):
                return self
            if not self.driver.find_elements(AppiumBy.ACCESSIBILITY_ID, current_label):
                break
        raise AssertionError(f"dropdown under {current_label!r} did not switch to {option!r}")

    def tap_pill(self, label: str):
        """Filter pills; Student Report pills read 'Fun Learn\\n93' (label + count)."""
        self.tap_desc_first_line(label)
        self.settle()
        return self

    def card_accuracy(self, student_name: str, tries: int = 3) -> str | None:
        """The ACCURACY value on a student's card in the Class Report list (the
        list reloads after a filter switch, so retry while it repaints)."""
        for _ in range(tries):
            value = self._card_accuracy_once(student_name)
            if value is not None:
                return value
            self.settle(2)
            self.scroll_to_top()
        return None

    def _card_accuracy_once(self, student_name: str) -> str | None:
        self.scroll_to_desc(student_name)
        nodes = self.nodes()
        names = [n for n in nodes if n.desc == student_name]
        if not names:
            return None
        # scrollIntoView stops once the name peeks in at the bottom edge, with
        # the card's value still under the nav bar; lift the card into view.
        height = self.driver.get_window_size()["height"]
        if names[0].y1 > height * 0.6:
            self.driver.swipe(540, int(height * 0.7), 540, int(height * 0.4), 700)
            time.sleep(1)
            nodes = self.nodes()
            names = [n for n in nodes if n.desc == student_name] or names
        # On a card the caption sits above its value ("ACCURACY" over "13.3%").
        caps = [n for n in nodes if n.desc == "ACCURACY" and n.y1 >= names[0].y1 - 80]
        if not caps:
            return None
        cap = min(caps, key=lambda n: n.y1)
        # The value can be narrower than the caption ("-") and sit off its
        # centre, so match on horizontal overlap rather than containment.
        below = [n for n in nodes if n.y1 >= cap.y2 - 2 and n.y1 - cap.y2 < 120
                 and n.x2 >= cap.x1 - 20 and n.x1 <= cap.x2 + 20 and n is not cap
                 and _PCT.match(n.desc)]
        return min(below, key=lambda n: n.y1).desc if below else None

    def dropdown_options(self, current_label: str) -> list[str]:
        """Open the dropdown showing `current_label`, collect every option's
        first line (scrolling its list), then close it again."""
        self.tap_desc(current_label)
        time.sleep(1.5)
        seen: list[str] = []
        idle = 0
        for _ in range(15):
            new = [n.desc.split("\n")[0] for n in self.nodes() if "\n" in n.desc]
            fresh = [o for o in new if o not in seen]
            idle = 0 if fresh else idle + 1
            if idle >= 2:  # two scrolls with nothing new: the list is exhausted
                break
            seen += fresh
            self._scroll_dropdown()
        self.tap_desc(current_label)
        time.sleep(1)
        return seen

    def open_drawer_item(self, label: str):
        self.tap_desc("Menu")
        time.sleep(1)
        self.tap_desc(label)
        self.settle(3)
        return self

    def scroll_to_top(self):
        try:
            self.driver.find_element(
                AppiumBy.ANDROID_UIAUTOMATOR,
                "new UiScrollable(new UiSelector().scrollable(true)).flingToBeginning(10)",
            )
        except Exception:
            pass  # reports "not found" after flinging; the scroll still happened
        return self

    def back(self):
        self.driver.back()
        self.settle(2)
        return self
