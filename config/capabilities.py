"""Builds the Appium UiAutomator2 capabilities from settings.

Black-box automation: we drive the installed Flutter app through Android's
accessibility tree (UiAutomator2). No Flutter source or debug build is required.
"""
from __future__ import annotations

import os

from appium.options.android import UiAutomator2Options

from config import settings


def build_options() -> UiAutomator2Options:
    opts = UiAutomator2Options()
    opts.platform_name = "Android"
    opts.automation_name = "UiAutomator2"
    opts.device_name = settings.DEVICE_NAME

    if settings.UDID:
        opts.udid = settings.UDID
    if settings.PLATFORM_VERSION:
        opts.platform_version = settings.PLATFORM_VERSION

    # Prefer installing a provided APK (Appium reads package/activity from it).
    # Fall back to launching an already-installed build by package/activity.
    if os.path.isfile(settings.APK_PATH):
        opts.app = settings.APK_PATH
    else:
        opts.app_package = settings.APP_PACKAGE
        opts.app_activity = settings.APP_ACTIVITY

    # Accept any activity we land on, so a splash -> main handoff doesn't fail.
    opts.app_wait_activity = "*"
    opts.app_wait_duration = 40000

    opts.no_reset = settings.NO_RESET
    opts.full_reset = settings.FULL_RESET

    # Flutter draws to a canvas; give the accessibility tree time to populate and
    # keep long test flows from being killed as "not responding".
    opts.new_command_timeout = 300
    opts.auto_grant_permissions = True
    opts.set_capability("appium:ignoreHiddenApiPolicyError", True)

    return opts
