"""Minimal Python client for the English Gurukul backend — the same endpoints
the app's services call. Used for data-level QA (e.g. validating that every
lesson-plan PDF and video URL actually loads), independent of the UI.

Endpoints (see lib/services/*):
  GET  backend/v1/schools/list/             -> {data:[{id, school_name}]}
  POST accounts/v1/auth/instructor-login/  {mobile_number, school_id} -> {data:{access,refresh}}
  GET  accounts/v1/auth/me/                -> {data:{..., school:{id,...}}}
  GET  management/v1/schools/<sid>/           -> {data:{total_strength, total_registered_students, ...}}
  GET  management/v1/schools/<sid>/classes/ -> {data:[{id, class_name, program, ...}], next}  (paged: ?page=N)
  GET  backend/v1/lesson-plans/<cid>/       -> {data:[{id, display_name, ...}]}
  GET  backend/v1/lesson-plans/<pid>/detail/-> {data:{pdfs:[...], videos:[...]}}
"""
from __future__ import annotations

import requests

# Since v2.5.4 the app resolves its backend at startup from this remote config
# (EgTeacherApp.<env>.base_url) instead of a hardcoded URL. The old Azure host
# stopped resolving after the Oct 2026 move to GCP, so read the same file the app
# reads; PROD is only the fallback when the config can't be fetched.
BASE_URL_CONFIG = "https://storage.googleapis.com/eg_videos/base_url_config_gcp.json"
CONFIG_APP = "EgTeacherApp"
PROD = "https://eg-infra-api-541085401763.asia-south1.run.app"
DEV = "https://eg-360-dev.englishgurukul.in"
API_VERSION = "v1"


def resolve_base_url(env: str = "prod") -> str:
    """The backend the live app uses for `env`, as its config resolver finds it."""
    fallback = PROD if env == "prod" else DEV
    try:
        r = requests.get(BASE_URL_CONFIG, timeout=15)
        r.raise_for_status()
        url = r.json()[CONFIG_APP][env]["base_url"]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return fallback
    return str(url).rstrip("/") or fallback


class EgApi:
    def __init__(self, base_url: str | None = None, timeout: int = 30):
        self.base_url = (base_url or resolve_base_url()).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.access = None
        self.mobile = None
        self._me = None

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

    def schools(self) -> list:
        """The login screen's school picker (no auth): [{id, school_name}]."""
        data = self._data(self._get("schools/list/"))
        return data if isinstance(data, list) else []

    def school_id_for(self, school_name: str) -> str:
        for school in self.schools():
            if str(school.get("school_name", "")).strip().lower() == school_name.strip().lower():
                return str(school["id"])
        raise RuntimeError(f"school not in schools/list/: {school_name!r}")

    def login(self, mobile_number: str, school_name: str | None = None) -> str:
        """Teacher login as the app does it since v2.5: `auth/instructor-login/`
        with the school picked on the login screen (the server rejects a number
        not registered with that school)."""
        if school_name is None:
            from data.test_data import SCHOOL_NAME
            school_name = SCHOOL_NAME
        # Remember the school picked at login: a number that teaches at several
        # schools gets its *primary* school from auth/me, not this one.
        self._login_school_id = self.school_id_for(school_name)
        r = self.session.post(
            self._url("auth/instructor-login/", module="accounts"),
            json={"mobile_number": mobile_number,
                  "school_id": self._login_school_id},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = self._data(r.json())
        self.access = data.get("access") or data.get("access_token")
        if not self.access:
            raise RuntimeError(f"login returned no access token: {r.text[:200]}")
        self.mobile = mobile_number
        self._me = None
        return self.access

    def me(self) -> dict:
        """The logged-in teacher's profile, fetched once per client."""
        if self._me is None:
            self._me = self._data(self._get("auth/me/", module="accounts")) or {}
        return self._me

    def school(self) -> dict:
        return self.me().get("school") or {}

    def school_name(self) -> str:
        """Display name of the logged-in teacher's school ("" if absent)."""
        school = self.school()
        for key in ("school_name", "name", "display_name", "title"):
            value = school.get(key) or self.me().get(key)
            if value:
                return str(value)
        return ""

    def teacher_name(self) -> str:
        me = self.me()
        for key in ("full_name", "name", "display_name", "first_name"):
            if me.get(key):
                return str(me[key])
        return ""

    def school_id(self) -> str:
        if getattr(self, "_login_school_id", None):
            return self._login_school_id
        me = self.me()
        sid = self.school().get("id") or me.get("school_id")
        if not sid:
            raise RuntimeError(f"could not find school id in auth/me: {me}")
        return str(sid)

    # -- lesson-plan data -----------------------------------------------------

    def school_summary(self, school_id: str) -> dict:
        """The school detail the home dashboard's summary card is built from —
        `total_strength` and `total_registered_students` (see
        lib/services/school_service.dart -> schoolById)."""
        data = self._data(self._get(f"schools/{school_id}/", module="management"))
        return data if isinstance(data, dict) else {}

    def classes(self, school_id: str) -> list:
        """Every class of the school. The endpoint is paged (`?page=N`, `next`),
        mirroring lib/services/class_service.dart."""
        out = []
        for page in range(1, 51):
            path = f"schools/{school_id}/classes/" + (f"?page={page}" if page > 1 else "")
            body = self._get(path, module="management")
            data = self._data(body)
            if not isinstance(data, list) or not data:
                break
            out.extend(data)
            if not (isinstance(body, dict) and body.get("next")):
                break
        return out

    def plans(self, class_id: str) -> list:
        data = self._data(self._get(f"lesson-plans/{class_id}/"))
        return data if isinstance(data, list) else []

    # -- reports (the endpoints the report screens call) -----------------------

    def _all_pages(self, path: str, key: str = "results") -> list:
        out, page = [], 1
        sep = "&" if "?" in path else "?"
        while True:
            data = self._data(self._get(f"{path}{sep}page={page}"))
            block = data.get(key) if isinstance(data, dict) and key in data else data
            if isinstance(block, dict):  # {count, page, total_pages, results}
                out.extend(block.get("results") or [])
                if page >= int(block.get("total_pages") or 1):
                    return out
            else:
                out.extend(block or [])
                return out
            page += 1

    def course_categories(self, program_id: str) -> list:
        """Class Report filter pills: [{id, display_name, topic_categories:[{id}]}]."""
        data = self._data(self._get(f"programs/{program_id}/course-categories/"))
        return data if isinstance(data, list) else []

    def module_report(self, class_id: str, topic_category_ids=None) -> dict:
        """Class Report for one filter: {'summary': {...}, 'students': [rows]}.
        No ids = the All pill (`topic_category=all`)."""
        ids = list(topic_category_ids or []) or ["all"]
        query = "&".join(f"topic_category={i}" for i in ids)
        path = f"classes/{class_id}/module-report/?{query}"
        first = self._data(self._get(f"{path}&page=1"))
        return {"summary": first.get("summary") or {},
                "students": self._all_pages(path, key="students")}

    def class_students(self, class_id: str) -> list:
        return self._all_pages(f"classes/{class_id}/students/")

    def course_report(self, class_id: str, student_id: str) -> dict:
        """Student Report: {'courses': [...], 'topics': [every topic]}."""
        path = f"classes/{class_id}/students/{student_id}/course-report/?course_id=all"
        first = self._data(self._get(f"{path}&page=1"))
        return {"courses": first.get("courses") or [],
                "topics": self._all_pages(path, key="topics")}

    def monthly_stars(self, class_id: str, month: int) -> list:
        """Star Arena rows for a class and month (1-12): [{student_name, stars}]."""
        data = self._data(self._get(f"classes/{class_id}/monthly-stars/{month}/?page_size=200"))
        rows = data.get("results") if isinstance(data, dict) else data
        return rows or []

    def class_tests(self, class_id: str) -> list:
        """The class's test assessments: [{test_id, display_name}]."""
        data = self._data(self._get(f"class-tests/{class_id}/tests/"))
        return data if isinstance(data, list) else []

    def assessments(self, class_id: str) -> list:
        """Assessment cards of a class as the Lesson Plan screen draws them: each
        plan's `test_assessments` ({id, display_name, status, summary}), tagged
        with the plan it sits under. Status is per class: `locked` (START),
        `unlocked` (in progress, STOP) or `completed` (stopped, RESTART)."""
        out = []
        for plan in self.plans(class_id):
            for test in plan.get("test_assessments") or []:
                out.append({**test, "plan": plan.get("display_name", "")})
        return out

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
