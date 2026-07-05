"""Central configuration, driven by environment / .env with safe defaults.

Nothing else in the suite should read os.environ directly â€” import from here so
there is one source of truth for the Appium server, app ids, and device target.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# qa_teacherapp_automation/ root, so relative APK paths resolve regardless of CWD.
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes"}


APPIUM_SERVER = os.getenv("APPIUM_SERVER", "http://127.0.0.1:4723")

# App under test â€” confirmed from android/app/build.gradle.kts + AndroidManifest.
# Note the package (applicationId) and activity namespace differ, which is normal
# for this Flutter project.
APP_PACKAGE = os.getenv("APP_PACKAGE", "com.OritSciencesPrivateLimited.EnglishGurukul.teacher")
APP_ACTIVITY = os.getenv("APP_ACTIVITY", "com.example.teacher_app.MainActivity")

# APK the user provides. If present, Appium installs it; if absent we assume the
# app is already installed on the device and launch by package/activity.
_apk = os.getenv("APK_PATH", "apps/teacher.apk")
APK_PATH = _apk if os.path.isabs(_apk) else str(ROOT / _apk)

DEVICE_NAME = os.getenv("DEVICE_NAME", "Android Emulator")
UDID = os.getenv("UDID", "").strip()
PLATFORM_VERSION = os.getenv("PLATFORM_VERSION", "").strip()

NO_RESET = _bool("NO_RESET", True)
FULL_RESET = _bool("FULL_RESET", False)

IMPLICIT_WAIT = int(os.getenv("IMPLICIT_WAIT", "10"))

REPORTS_DIR = ROOT / "reports"
SCREENSHOTS_DIR = REPORTS_DIR / "screenshots"
