"""Registration flow page objects: the license-code dialog and the
"Create your account" screen.

Reached from the login screen's REGISTER button. The license code resolves the
school (read-only badge), then the teacher supplies name + language. Since v2.5 a
successful submit lands on "Create your PIN" (SetPinPage), not the TeacherShell.
"""
from __future__ import annotations

from data.test_data import Text
from pages.base_page import BasePage


class LicenseDialog(BasePage):
    def is_open(self) -> bool:
        return self.is_visible(Text.LICENSE_TITLE, timeout=10)

    def enter_code_and_continue(self, code: str):
        box = self.first_edit_field()
        self.type_into(box, code)
        self.tap_desc(Text.LICENSE_CONTINUE)
        return self


class RegisterPage(BasePage):
    def wait_loaded(self, timeout: int = 25):
        self.wait_visible(Text.REGISTER_TITLE, timeout=timeout)
        return self

    def is_loaded(self) -> bool:
        return self.is_visible(Text.REGISTER_TITLE, timeout=20)

    def enter_name(self, name: str):
        # Name is the first EditText on this screen (mobile is the second, and is
        # pre-filled from the login screen).
        field = self.first_edit_field()
        self.type_into(field, name)
        self.hide_keyboard()
        return self

    def select_language(self, language: str):
        # Opens the Material dropdown, then taps the option by its label.
        self.tap_text(Text.SELECT_LANGUAGE_HINT)
        self.tap_desc(language)
        return self

    def submit(self):
        self.tap_desc(Text.REGISTER_SUBMIT)
        return self


class SetPinPage(BasePage):
    """'Create your PIN' — the last registration step. The PIN only gates
    Student Management actions, so the suite skips it with SET UP LATER."""

    def wait_loaded(self, timeout: int = 25):
        self.wait_visible(Text.PIN_TITLE, timeout=timeout)
        return self

    def is_loaded_soon(self, timeout: int = 10) -> bool:
        return self.is_visible(Text.PIN_TITLE, timeout=timeout)

    def set_up_later(self):
        self.tap_text(Text.PIN_LATER)
        return self
