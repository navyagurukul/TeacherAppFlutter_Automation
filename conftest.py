"""pytest fixtures: Appium driver lifecycle + screenshot-on-failure."""
from __future__ import annotations

import pytest

from config import settings
from utils.driver_factory import create_driver

settings.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture()
def driver():
    """Fresh Appium session per test. A successful login persists an auth token,
    which makes the splash screen auto-login and skip the login screen. Clearing
    app data before each test guarantees a clean, logged-out start."""
    drv = create_driver()
    try:
        drv.execute_script("mobile: clearApp", {"appId": settings.APP_PACKAGE})
    except Exception:
        # Fallback if clearApp is unavailable: at least relaunch fresh.
        drv.terminate_app(settings.APP_PACKAGE)
    drv.activate_app(settings.APP_PACKAGE)
    yield drv
    try:
        drv.quit()
    except Exception:
        pass


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """Capture a screenshot when a test fails, attached under reports/."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    drv = item.funcargs.get("driver")
    if drv is None:
        return
    safe = item.nodeid.replace("/", "_").replace("::", "__").replace(".py", "")
    path = settings.SCREENSHOTS_DIR / f"{safe}.png"
    try:
        drv.get_screenshot_as_file(str(path))
        print(f"\n[screenshot] {path}")
    except Exception as exc:  # pragma: no cover - best effort
        print(f"\n[screenshot failed] {exc}")
