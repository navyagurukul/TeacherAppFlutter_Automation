"""Minimal Python client for the English Gurukul backend — the same endpoints
the app's services call. Used for data-level QA (e.g. validating that every
lesson-plan PDF and video URL actually loads), independent of the UI.

Endpoints (see lib/services/*):
  POST accounts/v1/auth/mobile-login/      {mobile_number} -> {data:{access,refresh}}
  GET  accounts/v1/auth/me/                -> {data:{..., school:{id,...}}}
  GET  management/v1/schools/<sid>/classes/ -> {data:[{id, class_name, ...}]}
  GET  backend/v1/lesson-plans/<cid>/       -> {data:[{id, display_name, ...}]}
  GET  backend/v1/lesson-plans/<pid>/detail/-> {data:{pdfs:[...], videos:[...]}}
"""
from __future__ import annotations

import requests

# Base URLs from lib/services/api/api_config.dart.
PROD = "https://eg360-production-api.wonderfulsand-b8a3ee90.centralindia.azurecontainerapps.io"
DEV = "https://eg-360-dev.englishgurukul.in"
API_VERSION = "v1"


class EgApi:
    def __init__(self, base_url: str = PROD, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.access = None

    # -- url + request helpers ------------------------------------------------

    def _url(self, path: str, module: str = "backend") -> str:
        return f"{self.base_url}/api/{module}/{API_VERSION}/{path}"

    def _headers(self) -> dict:
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.access:
            h["Authorization"] = f"Bearer {self.access}"
        return h

    def _get(self, path: str, module: str = "backend") -> dict:
        r = self.session.get(self._url(path, module), headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _data(body: dict):
        return body.get("data", body) if isinstance(body, dict) else body

    # -- auth -----------------------------------------------------------------

    def login(self, mobile_number: str) -> str:
        r = self.session.post(
            self._url("auth/mobile-login/", module="accounts"),
            json={"mobile_number": mobile_number},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = self._data(r.json())
        self.access = data.get("access") or data.get("access_token")
        if not self.access:
            raise RuntimeError(f"login returned no access token: {r.text[:200]}")
        return self.access

    def school_id(self) -> str:
        me = self._data(self._get("auth/me/", module="accounts"))
        school = me.get("school") or {}
        sid = school.get("id") or me.get("school_id")
        if not sid:
            raise RuntimeError(f"could not find school id in auth/me: {me}")
        return str(sid)

    # -- lesson-plan data -----------------------------------------------------

    def classes(self, school_id: str) -> list:
        data = self._data(self._get(f"schools/{school_id}/classes/", module="management"))
        return data if isinstance(data, list) else []

    def plans(self, class_id: str) -> list:
        data = self._data(self._get(f"lesson-plans/{class_id}/"))
        return data if isinstance(data, list) else []

    def plan_detail(self, plan_id: str) -> dict:
        data = self._data(self._get(f"lesson-plans/{plan_id}/detail/"))
        return data if isinstance(data, dict) else {}


def best_video_urls(video: dict) -> list:
    """All non-empty MP4 URLs for a video (one per language, best quality),
    mirroring VideoLanguage.bestUrl (prefer 720, then 144, then any)."""
    out = []
    for lang in video.get("languages", []) or []:
        urls = lang.get("urls", {}) or {}
        pick = urls.get("720") or urls.get("144") or next(
            (u for u in urls.values() if u), ""
        )
        if pick:
            out.append((lang.get("language", ""), pick))
    return out
