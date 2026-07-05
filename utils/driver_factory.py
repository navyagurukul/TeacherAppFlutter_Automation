"""Creates and tears down the Appium driver."""
from __future__ import annotations

from appium import webdriver

from config import settings
from config.capabilities import build_options


def create_driver() -> webdriver.Remote:
    driver = webdriver.Remote(
        command_executor=settings.APPIUM_SERVER,
        options=build_options(),
    )
    driver.implicitly_wait(settings.IMPLICIT_WAIT)
    return driver
