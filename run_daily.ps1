# Daily QA run + Slack report. Point Windows Task Scheduler at this file.
# Runs the device-free Lesson-Plan link audit by default; pass args to change scope.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
& "$here\.venv\Scripts\python.exe" "$here\run_daily.py" @args
exit $LASTEXITCODE
