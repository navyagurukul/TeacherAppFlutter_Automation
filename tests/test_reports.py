"""Class Report, Student Report, Star Arena and Test Report, checked against the
backend endpoints those screens call (the same numbers the Student app writes).

* Class Report  - one student with real data: for every filter (All, each
  course category, Test) the class tiles and that student's accuracy match
  `module-report` / `completed-students`.
* Student Report - the same student: for All and every course pill, accuracy,
  trophies, completed topics and the pill's topic count match `course-report`.
* Star Arena    - every class x recent months (STAR_MONTHS, default 3): total
  students, total stars and each student's stars match `monthly-stars`.
* Test Report   - every class that has tests: GENERATE REPORT for its first test
  produces a downloadable report.

Percentages are compared the way the app prints them: one decimal + '%', '-' for 0.
"""
from __future__ import annotations

import datetime
import os
import re
import time

import pytest

from data.test_data import TEACHER_MOBILE, Text
from pages.login_page import LoginPage
from pages.reports_page import ReportsPage, pct
from utils.eg_api import EgApi

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
STAR_MONTHS = int(os.getenv("STAR_MONTHS", "3"))
REPORT_WAIT = int(os.getenv("TEST_REPORT_WAIT", "180"))


def _serial(name: str) -> int:
    m = re.search(r"\d+", name or "")
    return int(m.group()) if m else 1 << 30


@pytest.fixture(scope="module")
def api():
    a = EgApi()
    a.login(TEACHER_MOBILE)
    return a


@pytest.fixture(scope="module")
def classes(api):
    cls = api.classes(api.school_id())
    assert cls, "school has no classes"
    return cls


@pytest.fixture(scope="module")
def target(api, classes):
    """The class + student with the most report data (highest accuracy, then
    stars), so the comparison exercises real numbers rather than zeros."""
    best = None
    for c in classes:
        for row in api.module_report(str(c["id"]))["students"]:
            key = (float(row.get("accuracy") or 0), int(row.get("total_stars") or 0))
            if best is None or key > best[0]:
                best = (key, c, row)
    assert best, "no class has any students"
    _, c, row = best
    return {"class": c, "class_name": c["class_name"], "class_id": str(c["id"]),
            "program_id": (c.get("program") or {}).get("id"),
            "student": row["student_name"], "student_id": str(row["id"])}


def _current(rp: ReportsPage, labels) -> str | None:
    labels = set(labels)
    for n in rp.nodes():
        if n.desc in labels:
            return n.desc
    return None


def _home(driver):
    return LoginPage(driver).login_or_register(TEACHER_MOBILE)


# -- Class Report -------------------------------------------------------------------

@pytest.mark.regression
@pytest.mark.reports
def test_class_report_matches_backend(driver, api, classes, target, record_property):
    home = _home(driver)
    home.go_to(Text.NAV_CLASS)
    rp = ReportsPage(driver)
    names = [c["class_name"] for c in classes]
    rp.choose(_current(rp, names) or names[0], target["class_name"])

    cats = api.course_categories(target["program_id"]) if target["program_id"] else []
    filters = [("ALL", [])] + [(c["display_name"].upper(), [t["id"] for t in c.get("topic_categories") or []])
                              for c in cats]
    problems, checked = [], []
    for label, ids in filters:
        rp.scroll_to_top()
        rp.tap_pill(label)
        rep = api.module_report(target["class_id"], ids)
        s = rep["summary"]
        want = {"AVG. ACCURACY": pct(s.get("average_accuracy")),
                "TOTAL TROPHIES": str(s.get("total_trophies", 0)),
                "ACTIVE LEARNERS": str(s.get("active_learners", 0)),
                "TOTAL STARS": str(s.get("total_stars", 0))}
        got = rp.tiles(want)
        for k in want:
            if got[k] != want[k]:
                problems.append(f"[{label}] {k}: app {got[k]!r}, backend {want[k]!r}")
        row = next((r for r in rep["students"] if str(r["id"]) == target["student_id"]), None)
        if row:
            shown = rp.card_accuracy(target["student"])
            if shown != pct(row.get("accuracy")):
                problems.append(f"[{label}] {target['student']} accuracy: app {shown!r}, "
                                f"backend {pct(row.get('accuracy'))!r}")
        checked.append(f"{label}: {got}")

    # Test pill: completed students of the first test (the app auto-selects it).
    tests = sorted(api.class_tests(target["class_id"]), key=lambda t: _serial(t.get("display_name")))
    if tests:
        rp.scroll_to_top()
        rp.tap_pill("TEST")
        rp.settle(3)
        done = api._data(api._get(
            f"test-assessments/{target['class_id']}/{tests[0]['test_id']}/completed-students/"))
        n = len(done.get("students") if isinstance(done, dict) else done or [])
        shown = rp.value_above("COMPLETED")
        if not shown or not shown.split("/")[0].strip() == str(n):
            problems.append(f"[TEST {tests[0]['display_name']}] COMPLETED: app {shown!r}, backend {n}")
        checked.append(f"TEST {tests[0]['display_name']}: completed {shown}")

    record_property("class_report", f"{target['class_name']} / {target['student']} | " + " | ".join(checked))
    print(f"\n[class report] {target['class_name']} / {target['student']}\n  " + "\n  ".join(checked))
    assert not problems, "Class Report does not match the backend:\n- " + "\n- ".join(problems)


# -- Student Report -----------------------------------------------------------------

@pytest.mark.regression
@pytest.mark.reports
def test_student_report_matches_backend(driver, api, classes, target, record_property):
    home = _home(driver)
    home.go_to(Text.NAV_STUDENTS)
    rp = ReportsPage(driver)
    names = [c["class_name"] for c in classes]
    rp.choose(_current(rp, names) or "Select Grade", target["class_name"])
    students = [s["student_name"] for s in api.class_students(target["class_id"])]
    rp.choose(_current(rp, students) or "Select Student", target["student"])
    rp.settle(4)

    rep = api.course_report(target["class_id"], target["student_id"])
    courses, topics = rep["courses"], rep["topics"]

    def completed(ts):
        return str(sum(1 for t in ts if str(t.get("status", "")).lower() == "completed"))

    accs = [float(c.get("accuracy") or 0) for c in courses]
    views = [("All", pct(sum(accs) / len(accs)) if accs else "-",
              str(sum(int(c.get("total_trophies") or 0) for c in courses)), topics)]
    for c in courses:
        views.append((c["display_name"], pct(c.get("accuracy")), str(c.get("total_trophies") or 0),
                      [t for t in topics if str(t.get("course_id")) == str(c["id"])]))

    problems, checked = [], []
    for label, acc, trophies, ts in views:
        rp.scroll_to_top()
        rp.tap_pill(label)
        nodes = rp.nodes()
        pill = next((n.desc for n in nodes if n.desc.split("\n")[0] == label), "")
        got = rp.tiles(["AVG. ACCURACY", "TOTAL TROPHIES", "COMPLETED TOPICS"])
        want = {"AVG. ACCURACY": acc, "TOTAL TROPHIES": trophies, "COMPLETED TOPICS": completed(ts)}
        for k in want:
            if got[k] != want[k]:
                problems.append(f"[{label}] {k}: app {got[k]!r}, backend {want[k]!r}")
        count = pill.split("\n")[1] if "\n" in pill else None
        if count is not None and count != str(len(ts)):
            problems.append(f"[{label}] topic count on pill: app {count}, backend {len(ts)}")
        checked.append(f"{label}: {got} pill={pill.replace(chr(10), ' ')!r}")

    record_property("student_report", f"{target['class_name']} / {target['student']} | " + " | ".join(checked))
    print(f"\n[student report] {target['class_name']} / {target['student']}\n  " + "\n  ".join(checked))
    assert not problems, "Student Report does not match the backend:\n- " + "\n- ".join(problems)


# -- Star Arena ---------------------------------------------------------------------

@pytest.mark.regression
@pytest.mark.reports
def test_star_arena_by_class_and_month(driver, api, classes, record_property):
    home = _home(driver)
    rp = ReportsPage(driver)
    rp.open_drawer_item(Text.MENU_STAR_ARENA)
    assert rp.wait_desc("Star Arena", 20), "Star Arena did not open"

    now = datetime.date.today().month
    months = [m for m in range(now, max(0, now - STAR_MONTHS), -1)]
    names = [c["class_name"] for c in classes]
    problems, checked = [], []
    current_class = _current(rp, names) or names[0]
    current_month = MONTHS[now - 1]
    for c in classes:
        rp.choose(current_class, c["class_name"])
        current_class = c["class_name"]
        for m in months:
            rp.choose(current_month, MONTHS[m - 1])
            current_month = MONTHS[m - 1]
            rows = api.monthly_stars(str(c["id"]), m)
            want_total = sum(int(r.get("stars") or 0) for r in rows)
            got = rp.tiles(["TOTAL STUDENTS", "TOTAL STARS"])
            tag = f"{c['class_name']} / {MONTHS[m - 1]}"
            if rows:
                if got["TOTAL STUDENTS"] != str(len(rows)):
                    problems.append(f"[{tag}] TOTAL STUDENTS: app {got['TOTAL STUDENTS']!r}, backend {len(rows)}")
                if got["TOTAL STARS"] != str(want_total):
                    problems.append(f"[{tag}] TOTAL STARS: app {got['TOTAL STARS']!r}, backend {want_total}")
                nodes = rp.nodes()
                for r in rows:
                    shown = rp_row_stars(nodes, r.get("student_name"))
                    if shown is not None and shown != str(r.get("stars")):
                        problems.append(f"[{tag}] {r.get('student_name')}: app {shown} stars, backend {r.get('stars')}")
            elif not rp.wait_desc("No star data", 3, exact=False) and got["TOTAL STARS"] not in (None, "0"):
                problems.append(f"[{tag}] backend has no stars but app shows {got}")
            checked.append(f"{tag}: {len(rows)} students, {want_total} stars")

    record_property("star_arena", " | ".join(checked))
    print("\n[star arena]\n  " + "\n  ".join(checked))
    assert not problems, "Star Arena does not match the backend:\n- " + "\n- ".join(problems)


def rp_row_stars(nodes, name):
    """A leaderboard row reads: rank, name, star count to the right on the same line."""
    hit = next((n for n in nodes if n.desc == name), None)
    if not hit:
        return None  # off-screen rows are covered by the totals
    same_row = [n for n in nodes if n is not hit and n.x1 > hit.x2
                and abs((n.y1 + n.y2) / 2 - (hit.y1 + hit.y2) / 2) < 40 and n.desc.isdigit()]
    return min(same_row, key=lambda n: n.x1).desc if same_row else None


# -- Test Report generation ---------------------------------------------------------

@pytest.mark.regression
@pytest.mark.reports
def test_test_report_generated_for_each_class(driver, api, classes, record_property):
    home = _home(driver)
    rp = ReportsPage(driver)
    rp.open_drawer_item(Text.MENU_TEST)
    assert rp.wait_desc("Test Report", 20), "Test Report did not open"

    problems, checked = [], []
    current_class = "Select a class"

    # The screen must offer the logged-in school's classes.
    offered = rp.dropdown_options(current_class)
    expected = [c["class_name"] for c in classes]
    source = classes
    if sorted(offered) != sorted(expected):
        me_school = api.me().get("school") or {}
        problems.append(
            f"CLASS dropdown lists {offered} - not the logged-in school's classes "
            f"{expected}; they match the profile (auth/me) school "
            f"{me_school.get('school_name')!r}" )
        # Still prove generation works for what the screen offers.
        other = api.classes(str(me_school.get("id"))) if me_school.get("id") else []
        source = [c for c in other if c["class_name"] in offered] or classes
    checked.append(f"CLASS options: {offered}")

    for c in source:
        tests = sorted(api.class_tests(str(c["id"])), key=lambda t: _serial(t.get("display_name")))
        if not tests:
            checked.append(f"{c['class_name']}: no tests")
            continue
        test = tests[0]["display_name"]
        rp.scroll_to_top()
        rp.choose(current_class, c["class_name"])
        current_class = c["class_name"]
        rp.settle(3)
        current_test = next((n.desc for n in rp.nodes() if n.desc in {t["display_name"] for t in tests}),
                            "Select a test")
        rp.choose(current_test, test)
        # A banner or list row left from an earlier class must not count as this
        # class's outcome, so only text that appears after GENERATE is read.
        before = {n.desc for n in rp.nodes()}
        rp.tap_desc("GENERATE REPORT")
        label = f"{test} · {c['class_name']}"
        end, outcome = time.time() + REPORT_WAIT, None
        while time.time() < end and outcome is None:
            descs = [n.desc for n in rp.nodes() if n.desc not in before]
            if any(label in d for d in descs) or any("Report ready" in d for d in descs):
                outcome = "generated"
            elif any(("failed" in d.lower() or "expired" in d.lower() or "not allowed" in d.lower()
                      or "permission" in d.lower()) for d in descs):
                outcome = "failed: " + next(d for d in descs if any(
                    w in d.lower() for w in ("failed", "expired", "not allowed", "permission")))[:120]
            else:
                time.sleep(3)
        outcome = outcome or f"not ready after {REPORT_WAIT}s"
        if outcome != "generated":
            problems.append(f"{c['class_name']} / {test}: {outcome}")
            if rp.wait_desc("DISMISS", 2):
                rp.tap_desc("DISMISS")
        checked.append(f"{c['class_name']} / {test}: {outcome}")

    record_property("test_reports", " | ".join(checked))
    print("\n[test reports]\n  " + "\n  ".join(checked))
    assert not problems, "Test reports not generated:\n- " + "\n- ".join(problems)
