# Put the APK here

Drop the app build you want to test in this folder as `teacher.apk`
(or set `APK_PATH` in `.env` to another location).

```
qa_teacherapp_automation/apps/teacher.apk
```

- A **debug or profile** build gives the richest accessibility tree (best for
  Appium). A **release** build also works for text-based selectors.
- If the app is already installed on the device, you can leave this empty and the
  suite will launch it by package/activity instead.
