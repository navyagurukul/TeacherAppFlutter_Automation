"""What app build this run actually tested — read from the device, once per run.

The suite runs on two tracks:

* **Play Store** — the nightly drives the app already installed on the QA phone
  from Google Play (installer = com.android.vending), no APK.
* **Shared build** — a shared APK is installed by Appium (emulator workflow /
  run_shared_build.ps1), so APK_PATH points at a real file.

`capture()` records the track plus the installed versionName / versionCode of the
package that is actually in the foreground, so every report (Slack, HTML, the
run-history CSV) names the exact build it exercised. The result is written to
reports/build_info.json and reused by utils/app_version.py.
"""
from __future__ import annotations

import csv
import datetime
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from config import settings

INFO_FILE = settings.REPORTS_DIR / "build_info.json"
HISTORY_FILE = settings.REPORTS_DIR / "run_history.csv"

PLAY_INSTALLER = "com.android.vending"
BRANDS = {
    "com.OritSciencesPrivateLimited.EnglishGurukul.teacher": "English Gurukul Teacher",
    "com.OritSciencesPrivateLimited.EnglishGurukul.englishshikshateacher":
        "English Shiksha Teacher (Gujarat)",
}


def _adb(*args) -> str:
    adb = shutil.which("adb")
    if not adb:
        return ""
    cmd = [adb] + (["-s", settings.UDID] if settings.UDID else []) + list(args)
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return out.stdout or ""
    except Exception:
        return ""


def _field(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else None


def _apk_name() -> str | None:
    """Display name of the shared APK: the APK_NAME env (set by the emulator
    workflow from the original file name) or the local file name."""
    name = os.getenv("APK_NAME", "").strip()
    if name:
        return name
    return Path(settings.APK_PATH).name if os.path.isfile(settings.APK_PATH) else None


def _track(installer: str | None, apk: str | None) -> str:
    if apk:
        return "Shared build (APK)"
    if installer == PLAY_INSTALLER:
        return "Play Store"
    if installer:
        return f"Installed build (installer: {installer})"
    return "Installed build (sideloaded)"


def capture(driver=None) -> dict:
    """Read the build under test from the device and save it. `driver` (if
    given) supplies the foreground package, which is right even for a flavor
    whose package differs from APP_PACKAGE."""
    package = None
    if driver is not None:
        try:
            package = driver.current_package
        except Exception:
            package = None
    if not package or package not in BRANDS:
        package = settings.APP_PACKAGE

    dump = _adb("shell", "dumpsys", "package", package)
    installer = _field(r"installerPackageName=(\S+)", dump)
    if installer in ("null", ""):
        installer = None
    apk = _apk_name()
    info = {
        "track": _track(installer, apk),
        "app": BRANDS.get(package, package),
        "package": package,
        "version_name": _field(r"versionName=(\S+)", dump),
        "version_code": _field(r"versionCode=(\d+)", dump),
        "installer": installer,
        "apk": apk,
        "last_update": _field(r"lastUpdateTime=([0-9-]+ [0-9:]+)", dump),
        "device": settings.DEVICE_NAME + (f" ({settings.UDID})" if settings.UDID else ""),
        "captured_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    INFO_FILE.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


def load() -> dict | None:
    try:
        return json.loads(INFO_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def clear() -> None:
    """Forget the previous run's build so a run that never reaches the device
    can't report yesterday's version."""
    try:
        INFO_FILE.unlink()
    except OSError:
        pass


def summary(info: dict | None = None) -> str:
    """One line for reports, e.g.
    'Play Store · English Gurukul Teacher V2.5.2 (build 252)'."""
    info = info if info is not None else load()
    if not info or not info.get("version_name"):
        return "unknown build (device not reached)"
    line = f"{info['track']} · {info['app']} V{info['version_name']}"
    if info.get("version_code"):
        line += f" (build {info['version_code']})"
    if info.get("apk"):
        line += f" · APK: {info['apk']}"
    return line


def append_history(passed: int, failed: int, skipped: int, scope: str = "") -> None:
    """One row per run in reports/run_history.csv: when, which build, result."""
    info = load() or {}
    new = not HISTORY_FILE.exists()
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["run_at", "track", "app", "version", "build", "apk",
                        "device", "scope", "passed", "failed", "skipped"])
        w.writerow([
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            info.get("track", "unknown"), info.get("app", ""),
            info.get("version_name", ""), info.get("version_code", ""),
            info.get("apk", ""), info.get("device", ""), scope,
            passed, failed, skipped,
        ])
