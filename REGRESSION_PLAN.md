# Teacher App — Regression Test Plan (phased)

Full-regression coverage, built out in phases. Every flow logs in with the
**Sanskruthi** school. Each phase adds Page Objects + tests and is independently
runnable via markers.

Legend: ✅ built · 🔶 stubbed/next · ⬜ planned

---

## Phase 1 — Foundation & Auth  ✅ (built)

| Test | Marker | Notes |
|---|---|---|
| Login screen loads | `smoke login` | heading, LOG IN, REGISTER visible |
| Valid login → Home | `smoke login` | Sanskruthi + mobile → "Welcome!" |
| School required | `regression login` | snackbar "Please select a school" |
| Mobile required | `regression login` | "Mobile number is required" |
| Short mobile rejected | `regression login` | "Enter a valid 10-digit number" |
| Bottom-nav opens each tab | `smoke navigation` | Lessons/Class/Students/Manage/Home |

Screens: `login_screen.dart`, `teacher_shell.dart`, `bottom_nav.dart`.

## Phase 2 — Navigation & Shell  🔶

- End drawer opens; items present: Profile, Star Arena, Test, Zoom Training, Logout.
- "Not available yet" snackbar for unimplemented menu items.
- Logout returns to Login and clears session.
- IndexedStack preserves tab state (scroll position survives tab switch).

Screens: `teacher_shell.dart`, `app_drawer.dart`.

## Phase 3 — Registration  ⬜

- **Single student registration** (`student_registration_screen.dart`): required
  fields, valid submit, duplicate/validation errors.
- **Register (teacher)** via license dialog (`register_screen.dart`,
  `license_dialog.dart`): license code → form → submit.
- **Bulk registration** (`student_bulk_registration_screen.dart`,
  `bulk_registration_store.dart`): add rows, job submit, job status/progress.

Marker: `registration`.

## Phase 4 — Reports  ⬜

- **Class Report** (`class_report_screen.dart`): list loads, category pills,
  sort/filter bars, "View" opens Student Report.
- **Student Report** (`student_report_screen.dart`): report renders (donut chart,
  status badges), navigated both from Class Report and the Students tab.
- Report freshness / notification banner (`report_notification.dart`).

Marker: `reports`.

## Phase 5 — Lesson Plans & Media  ✅ (built)

Two-layer strategy — data-level link validation for *coverage*, UI for *launch*:

- **`test_lesson_plan_links.py`** — crawls every class → plan → materials via the
  API (`utils/eg_api.py`, `utils/lesson_audit.py`) and HTTP-validates that every
  PDF loads (200 + `%PDF`), every video MP4 loads (ranged GET), and every
  hyperlink embedded *inside* each PDF loads (`utils/link_check.py`, pypdf).
  Full report → `reports/lesson_plan_links.md`. Latest run: **9 classes, 54
  plans, 91 PDFs, 460 videos, 70 in-PDF links — 0 broken.**
- **`test_lesson_plan_ui.py`** — drives the app to open a real PDF in the in-app
  viewer, and to open the video player, exercise the transport (fast-forward, or
  rewind if forward doesn't take — verified via the position label, never sitting
  through the clip), then switch through **every language chip** (English, Hindi,
  Telugu, Kannada, Gujarati, …) confirming each variant plays. Targets are
  discovered from the API so the test stays valid as content changes.

Why the split: Flutter renders PDFs/videos to a canvas, so black-box Appium
can't confirm playback frames or tap links *inside* a PDF — link validation
covers those exhaustively, and the UI layer proves the viewers launch.

Marker: `lessons`. Trim scope: `LESSON_CLASS_LIMIT=1 LESSON_PLAN_LIMIT=2 pytest -m lessons`.

## Phase 6 — Tests / Assessments  ⬜

- Test screen loads a test, questions render (`test_screen.dart`,
  `topic_questions_panel.dart`, `quiz_result_widgets.dart`).
- Submit → result panel; completion state (`class_test_completion`).

Marker: `tests_flow`.

## Phase 7 — Management  ⬜

- Student roster loads (`management_screen.dart`, `student_roster.dart`).
- Approve/reject unapproved students (`student_approval_panel.dart`).
- Edit student (`edit_student_screen.dart`); Delete student
  (`delete_student_screen.dart`) incl. confirmation.

Marker: `management`.

## Phase 8 — Profile, Star Arena, Cross-cutting  ⬜

- Profile screen data + license card (`profile_screen.dart`,
  `student_license_card.dart`).
- Star Arena / monthly stars (`monthsstars.dart`, `star_service.dart`).
- Theme toggle (light/dark) persists.
- App-update gate / update dialog (`app_update_service.dart`, `update_dialog.dart`).
- Contact/bug-report button + share sheet (`contact_button.dart`).
- Service-unreachable / offline states (`service_unreachable.dart`).

Marker: `profile` (+ ad-hoc markers as areas grow).

---

## Environment / data risks to confirm with the app team

- A **stable Sanskruthi test teacher** mobile whose OTP-less login works against
  the QA/staging backend (set via `.env` / CI secret, not committed).
- Staging vs prod backend the APK points at (`lib/services/api/api_config.dart`).
- Seeded students/classes/lessons/tests for Sanskruthi so report/lesson/test
  assertions are deterministic.
- For any control that's hard to locate by text, request a `Semantics` label /
  `Key` from the developers rather than relying on brittle coordinates.
