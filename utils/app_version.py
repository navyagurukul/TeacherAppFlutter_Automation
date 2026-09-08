"""Resolve the Teacher app version — the one shown on the login-screen footer
(`ENGLISH GURUKUL TEACHER PORTAL V<version>`, rendered from PackageInfo).

The daily report shows this so every Slack summary is tied to a concrete build.
Resolution order (first hit wins), most-faithful first:

1. `reports/app_version.txt` — the exact footer captured live from the login UI
   during this run (written by tests/test_login.py). This is literally what the
   login screen displayed.
2. `APP_VERSION` env / .env override.
3. A connected device: `adb shell dumpsys package <pkg>` -> versionName.
4. The APK: `aapt dump badging <apk>` -> versionName.
5. `../pubspec.yaml` `version:` (the build's source of truth, e.g. 2.3.6+236).

Returns the bare version name (e.g. "2.3.6"); `label()` formats it like the app.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from config import settings

ROOT = settings.ROOT
CAPTURED = settings.REPORTS_DIR / "app_version.txt"
PUBSPEC = ROOT.parent / "pubspec.yaml"


def _run(cmd) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (out.stdout or "") + (out.stderr or "")
    except Exception:
        return ""


def _from_captured():
    """The footer string captured from the live login screen, if a UI test ran.
    We store the full label and pull the version out of it. If the capture holds
    no actual version (e.g. only 'TEACHER PORTAL' — the version renders as a
    separate node), return None so a real source (adb/apk/pubspec) is used
    instead of emitting a bogus 'VTEACHER PORTAL'."""
    if not CAPTURED.exists():
        return None
    text = CAPTURED.read_text(encoding="utf-8").strip()
    if not text:
        return None
    m = re.search(r"[Vv]?\s*([0-9]+(?:\.[0-9]+)+[0-9A-Za-z.\-+]*)", text)
    return m.group(1) if m else None


def _from_env():
    import os

    v = os.getenv("APP_VERSION", "").strip()
    return v or None


def _adb_prefix():
    adb = shutil.which("adb")
    if not adb:
        return None
    cmd = [adb]
    if settings.UDID:
        cmd += ["-s", settings.UDID]
    return cmd


def _from_device():
    prefix = _adb_prefix()
    if not prefix:
        return None
    out = _run(prefix + ["shell", "dumpsys", "package", settings.APP_PACKAGE])
    m = re.search(r"versionName=([0-9][0-9A-Za-z.\-+]*)", out)
    return m.group(1) if m else None


def _from_apk():
    apk = Path(settings.APK_PATH)
    if not apk.exists():
        return None
    tool = shutil.which("aapt") or shutil.which("aapt2")
    if not tool:
        return None
    out = _run([tool, "dump", "badging", str(apk)])
    m = re.search(r"versionName='([^']+)'", out)
    return m.group(1) if m else None


def _from_pubspec():
    if not PUBSPEC.exists():
        return None
    for line in PUBSPEC.read_text(encoding="utf-8").splitlines():
        if line.startswith("version:"):
            raw = line.split(":", 1)[1].strip()
            return raw.split("+", 1)[0].strip() or None
    return None


SOURCES = [
    (_from_captured, "login screen"),
    (_from_env, "APP_VERSION override"),
    (_from_device, "installed build"),
    (_from_apk, "APK under test"),
    (_from_pubspec, "pubspec.yaml"),
]


def resolve_with_source() -> tuple[str | None, str]:
    """(version, where it came from) so the report never claims the login screen
    showed a version it actually read out of pubspec.yaml."""
    for source, origin in SOURCES:
        try:
            v = source()
        except Exception:
            v = None
        if v:
            return v, origin
    return None, "not found"


def resolve() -> str | None:
    """The version name (e.g. "2.3.6"), or None if nothing could read it."""
    return resolve_with_source()[0]


def clear_capture() -> None:
    """Drop a previous run's captured footer so today's report can't inherit
    yesterday's version after a release."""
    try:
        CAPTURED.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def label() -> str:
    """Formatted like the login-screen footer, e.g. 'V2.3.6' (or 'unknown')."""
    v = resolve()
    return f"V{v}" if v else "unknown"


def label_with_source() -> str:
    """e.g. 'V2.3.6  (login screen)' — version plus where it was read from."""
    v, origin = resolve_with_source()
    return f"V{v}  ({origin})" if v else f"unknown  ({origin})"
