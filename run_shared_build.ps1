<#
.SYNOPSIS
  Test a freshly shared teacher-app build (APK) in CI, with one command.

.DESCRIPTION
  Uploads the given APK to a GitHub Release (so it has a public download URL),
  then triggers the "Android UI Tests (emulator)" workflow against it. Results
  post to Slack and upload as artifacts. Runs the APK on a CLEAN emulator, so a
  differently-signed build never clashes with the Play Store app on the QA phone
  (which stays reserved for the daily nightly run).

.EXAMPLE
  .\run_shared_build.ps1 -ApkPath "C:\Downloads\teacher-2.3.7.apk"

.EXAMPLE
  .\run_shared_build.ps1 -ApkPath .\build.apk -Markers "smoke"   # quick check
#>
param(
  [Parameter(Mandatory = $true)][string]$ApkPath,
  [string]$Markers = "not heavy",
  [string]$Repo = "navyagurukul/TeacherAppFlutter_Automation"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $ApkPath)) { throw "APK not found: $ApkPath" }
$ApkPath = (Resolve-Path -LiteralPath $ApkPath).Path

# --- token from the machine's git credential store (no secrets in this file) ---
$cred = "protocol=https`nhost=github.com`n`n" | git credential fill
$token = (($cred | Select-String '^password=') -replace '^password=', '').Trim()
if (-not $token) { throw "Could not read a GitHub token from git credential for github.com." }
$H  = @{ Authorization = "Bearer $token"; Accept = "application/vnd.github+json" }
$api = "https://api.github.com/repos/$Repo"

# --- 1. create a Release to host the APK -------------------------------------
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$tag = "apk-shared-$stamp"
Write-Host "Creating release $tag ..."
$relBody = @{ tag_name = $tag; target_commitish = "main"
  name = "Shared teacher build ($stamp)"
  body = "Uploaded by run_shared_build.ps1 for an on-demand emulator test run."
  prerelease = $true } | ConvertTo-Json
$rel = Invoke-RestMethod -Method Post -Uri "$api/releases" -Headers $H -Body $relBody
$uploadUrl = ($rel.upload_url -split '\{')[0]

# --- 2. upload the APK as a release asset ------------------------------------
Write-Host "Uploading $([IO.Path]::GetFileName($ApkPath)) ($([math]::Round((Get-Item $ApkPath).Length/1MB)) MB) ..."
$uH = @{ Authorization = "Bearer $token" }
$asset = Invoke-RestMethod -Method Post -Uri "$uploadUrl?name=teacher.apk" -Headers $uH `
  -InFile $ApkPath -ContentType "application/vnd.android.package-archive"
$dl = $asset.browser_download_url
Write-Host "APK URL: $dl"

# --- 3. trigger the emulator workflow against it -----------------------------
Write-Host "Triggering emulator run (markers: '$Markers') ..."
$disp = @{ ref = "main"; inputs = @{ apk_url = $dl; markers = $Markers; api_level = "33" } } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$api/actions/workflows/android-ui.yml/dispatches" -Headers $H -Body $disp | Out-Null

Start-Sleep -Seconds 6
$run = (Invoke-RestMethod -Uri "$api/actions/workflows/android-ui.yml/runs?per_page=1" -Headers $H).workflow_runs[0]
Write-Host ""
Write-Host "Started: $($run.html_url)"
Write-Host "Results will post to Slack when the run finishes."
