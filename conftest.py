"""pytest fixtures: Appium driver lifecycle + screenshot-on-failure."""
from __future__ import annotations

import pytest

from config import settings
from utils import build_info
from utils.driver_factory import create_driver

settings.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

_build_captured = False


def pytest_collection_modifyitems(session, config, items):
    """A run that will touch the device starts by forgetting the last run's
    build, so its reports can only name the build this run actually tested.
    Device-free runs (the media audit) keep it — the nightly posts the audit
    right after the UI run and should still name that build."""
    if any("driver" in getattr(item, "fixturenames", ()) for item in items):
        build_info.clear()


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
    _skip_optional_update(drv)
    global _build_captured
    if not _build_captured:
        print(f"\n[build] {build_info.summary(build_info.capture(drv))}")
        _build_captured = True
    yield drv
    try:
        drv.quit()
    except Exception:
        pass


def _skip_optional_update(drv) -> None:
    """When the installed build is behind the store, the app opens on an
    'Update available' dialog over the login screen. Tap SKIP so the run tests
    the installed build, and note the offered version for the reports."""
    from data.test_data import Text
    from pages.base_page import BasePage

    page = BasePage(drv)
    if not page.is_visible(Text.UPDATE_DIALOG_TITLE, timeout=8):
        return
    try:
        body = page.find_by_text("A new version", exact=False, timeout=3)
        offer = (body.get_attribute("content-desc") or body.text or "").strip()
    except Exception:
        offer = Text.UPDATE_DIALOG_TITLE
    (settings.REPORTS_DIR / "update_offered.txt").write_text(offer, encoding="utf-8")
    print(f"\n[update dialog] {offer!r} -> SKIP")
    page.tap_text(Text.UPDATE_SKIP, timeout=10)


def pytest_html_results_summary(prefix, summary, postfix):
    """Name the tested build at the top of reports/report.html."""
    prefix.append(f"<p><b>Build tested:</b> {build_info.summary()}</p>")


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
