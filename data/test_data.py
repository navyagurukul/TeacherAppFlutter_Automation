"""Test data for the teacher app regression suite.

IMPORTANT: All tests use the **Samskruthi** school. Do not switch to any other
school (e.g. Navodaya) — this is a fixed convention for this app's QA.
"""
from __future__ import annotations

# The one school every test logs into. SCHOOL_SEARCH is what we type into the
# picker's search box; SCHOOL_NAME is the exact list row we tap.
SCHOOL_SEARCH = "Samskruthi"
SCHOOL_NAME = "Samskruthi School - IMS School - Nalgonda"

# Teacher used for login/registration. If this number isn't registered yet, the
# login-or-register flow enrolls it via the license code below.
TEACHER_MOBILE = "9000000001"
TEACHER_NAME = "QA Automation"
TEACHER_LANGUAGE = "English"

# License code for  Samskruthi School - IMS School - Nalgonda (used by the REGISTER flow).
LICENSE_CODE = "SANK48"

# Inputs used by login validation tests.
INVALID_MOBILE_SHORT = "12345"
NON_DIGIT_MOBILE = "abcdefghij"

# Copy shown by the app (used for assertions).
class Text:
    SIGN_IN_HEADING = "Sign in to continue"
    LOGIN_BUTTON = "LOG IN"
    REGISTER_BUTTON = "REGISTER"
    MOBILE_HINT = "10-digit mobile number"
    SELECT_SCHOOL_HINT = "Select school"
    SEARCH_SCHOOL_HINT = "Search school"

    # Validation / snackbar messages.
    MOBILE_REQUIRED = "Mobile number is required"
    MOBILE_INVALID = "Enter a valid 10-digit number"
    SCHOOL_REQUIRED = "Please select a school"

    # License dialog (REGISTER flow).
    LICENSE_TITLE = "Enter License Code"
    LICENSE_CONTINUE = "CONTINUE"
    LICENSE_CANCEL = "CANCEL"

    # Register screen ("Create your account").
    REGISTER_TITLE = "Create your account"
    SELECT_LANGUAGE_HINT = "Select language"
    REGISTER_SUBMIT = "REGISTER"
    BACK_TO_LOGIN = "BACK TO LOGIN"

    # Home / shell after a successful login.
    HOME_TITLE = "Welcome!"

    # Home-dashboard boxes (labels are rendered UPPERCASE).
    BOX_LESSON_PLAN = "LESSON PLAN"
    BOX_CLASS_REPORT = "CLASS REPORT"
    BOX_STUDENT_REPORT = "STUDENT REPORT"
    BOX_MANAGEMENT = "MANAGEMENT"
    HOME_HEADER = "TEACHER HOME"

    # School-summary card on the home dashboard. The legend renders each row as
    # a label node followed by a separate count node ("Remaining: " then "78").
    LEGEND_REGISTERED = "Registered"
    LEGEND_REMAINING = "Remaining"

    # Section header titles shown in the shell app-bar per destination.
    TITLE_LESSON_PLAN = "Lesson Plan"
    TITLE_CLASS_REPORT = "Class Report"
    TITLE_STUDENT_REPORT = "Student Report"
    TITLE_MANAGEMENT = "Student Management"

    # Lesson Plan screen.
    SELECT_CLASS_HINT = "Select class"
    LESSON_PDF_LABEL = "LESSON PDF"
    VIDEOS_LABEL = "VIDEOS"
    # The viewer's app-bar title merges into one semantics node,
    # "<title>\nPage <n> of <total>", and the indicator only appears once the
    # document is paginated — so it proves the PDF actually rendered.
    PDF_PAGE_INDICATOR = "Page 1 of"
    PDF_BOOKMARKS = "Bookmarks"   # app-bar action, unique to the PDF viewer
    PDF_OPEN_ERROR = "Couldn't open this PDF."
    VIDEO_PLAY_ERROR = "Couldn't play this video."

    # Bottom-nav labels.
    NAV_HOME = "Home"
    NAV_LESSONS = "Lessons"
    NAV_CLASS = "Class"
    NAV_STUDENTS = "Students"
    NAV_MANAGE = "Manage"

    # End-drawer menu items.
    MENU_PROFILE = "Profile"
    MENU_STAR_ARENA = "Star Arena"
    MENU_TEST = "Test"
    MENU_ZOOM = "Zoom Training"
    MENU_LOGOUT = "Logout"
