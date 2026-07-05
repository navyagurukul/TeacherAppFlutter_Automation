# Teacher App — QA Automation (Appium + Python)

End-to-end UI automation for the English Gurukul **Teacher** Android app
(Flutter). Black-box automation via Appium's **UiAutomator2** driver — it drives
the installed app through Android's accessibility tree, so no Flutter source or
special build is required.

- **Stack:** Appium 2 · UiAutomator2 · Python · pytest · Page Object Model
- **Convention:** every test logs in with the **Sanskruthi** school. Do not
  switch schools.

---

## Layout

```
qa_teacherapp_automation/
├── apps/                 # drop teacher.apk here (git-ignored)
├── config/
│   ├── settings.py       # single source of truth (env-driven)
│   └── capabilities.py   # UiAutomator2 desired capabilities
├── data/test_data.py     # school, mobile numbers, UI copy/strings
├── pages/                # Page Objects (base_page, login_page, home_page, …)
├── tests/                # pytest test modules
├── utils/                # driver_factory, eg_api, lesson_audit, app_version
├── conftest.py           # driver fixture + screenshot-on-failure
├── pytest.ini            # markers, html report
├── requirements.txt
├── .env.example          # copy to .env
└── REGRESSION_PLAN.md    # phased full-regression coverage plan
```

## One-time setup

Already installed on this machine: **Appium 2.11**, **uiautomator2 driver**,
**Python 3.11**, **Android SDK + emulators**, **adb**.

```powershell
# from qa_teacherapp_automation/
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env      # then edit if needed
```

## Provide the app + a device

1. Put your build at `apps/teacher.apk` (or point `APK_PATH` at it in `.env`).
2. Start an emulator (4 AVDs exist here — e.g. `Pixel_9a`):
   ```powershell
   emulator -avd Pixel_9a
   adb devices           # confirm one device is "device"
   ```

## Run

```powershell
# Terminal 1 — Appium server
appium

# Terminal 2 — tests (venv active, from qa_teacherapp_automation/)
pytest                       # everything
pytest -m smoke              # smoke only (fast)
pytest -m "login"            # one area
pytest tests/test_login.py::test_valid_login_reaches_home
```

- HTML report: `reports/report.html`
- Failure screenshots: `reports/screenshots/`

## App identifiers (already wired in)

| | |
|---|---|
| appPackage | `com.OritSciencesPrivateLimited.EnglishGurukul.teacher` |
| appActivity | `com.example.teacher_app.MainActivity` |

> The package (applicationId) and activity namespace differ — that's normal for
> this project and already handled in `config/`.

## How selectors work (Flutter note)

Flutter paints to a canvas, so widgets appear in the accessibility tree mostly by
their **text** or **semantics label** (`content-desc`). `pages/base_page.py`
therefore locates by visible text with a content-desc fallback. If a specific
control proves hard to reach reliably, the durable fix is to add a `Semantics`
label / `Key` in the Flutter code — coordinate that with the app developer.

## Daily run + Slack report

`run_daily.py` runs a pass and posts a **per-area** summary to Slack titled
*Teacher App QA — Daily*, headed with the **app version shown on the login
screen** (e.g. `V2.3.6`). The report groups results into five areas — **Login,
Tabs, Lesson Plans, PDFs, Videos** — each with its own pass/fail and count.
Overall is PASS only when every area passes.

Scope is chosen automatically — no args needed:

- The device-free **Lesson-Plan media audit** (Lesson Plans / PDFs / Videos,
  validated against real data) **always** runs — reliable unattended, phone or not.
- The **Login** and **Tabs** UI areas also run **when a device + Appium are up**.
  With no device they show as `skipped — no device` (not failed), so an
  unattended host still gets a clean media report.

```powershell
# one-off (uses the venv)
.\.venv\Scripts\python.exe run_daily.py              # auto scope -> Slack
.\.venv\Scripts\python.exe run_daily.py --audit-only # force device-free media audit
.\.venv\Scripts\python.exe run_daily.py --with-ui    # force-include Login/Tabs (needs device+Appium)
.\.venv\Scripts\python.exe run_daily.py tests/test_login.py  # explicit pytest scope
```

Set the webhook once in `.env`:
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
```
If no webhook is set, it prints the report to the console instead. Example:

```
Teacher App QA — Daily (2026-07-05 07:00)   FAIL
App version: V2.3.6  (login screen)
Passed 8/9  |  Failed 1  |  Skipped 0  |  214s

- Login         PASS 3/3
- Tabs          PASS 1/1
- Lesson Plans  PASS 2/2
- PDFs          FAIL 1/2  — test_all_pdfs_load
- Videos        PASS 1/1

Lesson media (data): Classes crawled: 9 | PDFs: 91 checked, 0 broken | Videos: 460 checked, 0 broken
```

(The live Slack message uses emoji and bullets; the above is a plain-text sketch.)

**App version** is resolved (first hit wins): the exact footer captured live from
the login screen (`reports/app_version.txt`, written by the Login area test), then
`APP_VERSION` env, then a connected device (`adb`), then the APK, then
`../pubspec.yaml`. So on a device run it's literally what the login screen
displayed; unattended it still reports the build's version.

### Schedule it daily (Windows Task Scheduler)

Register a task that runs every day at 07:00 (adjust `/st`):

```powershell
schtasks /Create /TN "TeacherApp QA Daily" /SC DAILY /ST 07:00 /F ^
  /TR "powershell -NoProfile -ExecutionPolicy Bypass -File \"C:\Users\user\Downloads\TeacherAppFlutter-Staging\TeacherAppFlutter-Staging\qa_teacherapp_automation\run_daily.ps1\""
```

Run it now to verify:  `schtasks /Run /TN "TeacherApp QA Daily"`
Remove it:            `schtasks /Delete /TN "TeacherApp QA Daily" /F`

- With a **phone connected + Appium running**, the daily job covers all five
  areas (Login, Tabs, Lesson Plans, PDFs, Videos) and reports the login-screen
  version live.
- On an **unattended host with no device**, it still runs the device-free media
  audit (Lesson Plans / PDFs / Videos) and marks Login/Tabs as
  `skipped — no device`. Set `DAILY_INCLUDE_UI=0` to force audit-only, or
  `=1` to require the UI areas.

## CI/CD (GitHub Actions)

Repo: `github.com/navyagurukul/TeacherAppFlutter_Automation`. Three workflows live
in `.github/workflows/`:

| Workflow | Trigger | What it does | Needs |
|---|---|---|---|
| **CI** (`ci.yml`) | every push / PR | installs deps, byte-compiles all modules, `pytest --collect-only` (validates imports + markers). No device. | nothing |
| **Daily QA Report** (`daily-report.yml`) | daily 07:00 IST + manual | runs the device-free media audit (Lesson Plans / PDFs / Videos) and posts the per-area summary to Slack. | `SLACK_WEBHOOK_URL` secret; optional `APP_VERSION` variable |
| **Android UI Tests** (`android-ui.yml`) | manual | boots a cloud Android emulator, installs the APK you point it at, starts Appium, runs the UI suite (Login/Tabs/viewers). | `apk_url` input; optional `SLACK_WEBHOOK_URL` secret |

**One-time repo setup** (GitHub → Settings → Secrets and variables → Actions):

- Secret **`SLACK_WEBHOOK_URL`** — the Slack Incoming Webhook the daily report posts to.
- Variable **`APP_VERSION`** *(optional)* — e.g. `2.3.6`, shown in the report header.
  This standalone repo has no `pubspec.yaml` to auto-read; a real device run
  resolves the version live from the login screen instead.

Cloud runners have no physical phone, so the **UI areas (Login/Tabs)** run only in
the manual *Android UI Tests* emulator workflow — supply a downloadable APK URL.
The push/PR gate and the daily media report are fully device-free.

## Markers

`smoke`, `regression`, `login`, `navigation`, `registration`, `reports`,
`lessons`, `tests_flow`, `management`, `profile`. See `REGRESSION_PLAN.md` for the
phased buildout.
