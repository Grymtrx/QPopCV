# QPopCV Release Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a documented, repeatable release workflow — from Python source to GitHub release ZIP — with a build script, release process docs, update mechanics explanation, and a skill that codifies the workflow for future sessions.

**Architecture:** `build.ps1` automates PyInstaller compilation + ZIP packaging with auto-versioning. `docs/RELEASE.md` documents end-to-end release process, update mechanics (in-place replacement = taskbar pin stays valid), and config persistence guarantees. A `build-release` skill in the user's skills directory encodes the workflow for future Claude sessions.

**Tech Stack:** PyInstaller, PowerShell 5+, GitHub CLI (`gh`), Python 3.11+

---

## Context: How the Update Mechanism Works

Before building anything, understand the current update flow so you don't break it:

1. User downloads `QPopCV-vX.Y.Z.zip`, extracts to e.g. `C:\QPopCV\`, runs `QPopCV.exe`
2. App calls `UpdateManager.check_for_update()` → GitHub Releases API → compares semver
3. User clicks "Install Update" → `install_update()` downloads the new ZIP to a temp dir, extracts it
4. `_run_external_updater()` writes `qpopcv_update.bat` to the temp dir and launches it via `os.startfile()`
5. The batch script waits for `QPopCV.exe` to exit, then runs:
   `xcopy "%SRC%\*" "%DEST%\" /E /I /Y` — copies all new files over the existing install dir
6. Restarts `QPopCV.exe` from the same path, then cleans up

**Taskbar pin stays valid** because the `.exe` path never changes — we replace files in-place, same directory, same filename. Windows taskbar pins are path-based, so the pin continues to launch the new version after the update.

**Config persistence** is guaranteed because `config.local.json` is gitignored and is never included in the release ZIP. The `xcopy` only copies what's in the ZIP, leaving `config.local.json` untouched in the user's install folder. The user's webhook URL, Discord ID, monitor preference, and AFK setting all survive every update.

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `build.ps1` | **Create** | Automated build: PyInstaller → clean ZIP ready to upload |
| `docs/RELEASE.md` | **Create** | End-to-end release checklist + update mechanics reference |
| `C:\Users\Jesse\.claude\skills\build-release.md` | **Create** | Claude skill encoding the build-release workflow |

---

## Task 1: Create `build.ps1` — Build and Package Script

**Files:**
- Create: `build.ps1`

This script reads the version from source, compiles via PyInstaller, and produces a correctly-structured ZIP for GitHub releases.

- [ ] **Step 1: Write `build.ps1`**

```powershell
# build.ps1 — QPopCV build and package script
# Usage: .\build.ps1
# Output: dist\QPopCV-vX.Y.Z.zip
#
# The ZIP wraps all exe + DLL files inside a QPopCV\ top-level folder.
# updater.py's _find_source_root() detects this single-folder layout and
# strips the wrapper, so xcopy lands files directly in the user's install dir.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# ── 1. Read version from qpopcv/config.py ──────────────────────────────────
$configContent = Get-Content "qpopcv\config.py" -Raw
if (-not ($configContent -match 'APP_VERSION\s*=\s*"([^"]+)"')) {
    throw "Could not read APP_VERSION from qpopcv\config.py"
}
$version = $Matches[1]
Write-Host "[build] Version: $version"

# ── 2. Run PyInstaller ──────────────────────────────────────────────────────
Write-Host "[build] Running PyInstaller..."
pyinstaller QPopCV.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

# ── 3. Verify the exe exists ────────────────────────────────────────────────
$exePath = "dist\QPopCV\QPopCV.exe"
if (-not (Test-Path $exePath)) {
    throw "Expected exe not found at $exePath after build"
}
Write-Host "[build] Exe verified: $exePath"

# ── 4. Create release ZIP ───────────────────────────────────────────────────
# ZIP structure: QPopCV\QPopCV.exe, QPopCV\*.dll, QPopCV\media\, etc.
# The single top-level folder is what _find_source_root() expects.
$zipName = "QPopCV-v$version.zip"
$zipPath = "dist\$zipName"

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
    Write-Host "[build] Removed existing $zipPath"
}

Write-Host "[build] Creating $zipPath..."
# Compress the dist\QPopCV folder itself (not just its contents)
# This produces a ZIP with a single top-level entry: QPopCV\
Compress-Archive -Path "dist\QPopCV" -DestinationPath $zipPath

$sizeMB = [Math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host "[build] Done: $zipPath ($sizeMB MB)"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Test the exe: dist\QPopCV\QPopCV.exe"
Write-Host "  2. Tag the release: git tag v$version && git push origin v$version"
Write-Host "  3. Create GitHub release and upload: dist\$zipName"
```

- [ ] **Step 2: Run the build script to verify it works**

```powershell
cd D:\Git\QPopCV
.\build.ps1
```

Expected output ends with:
```
[build] Done: dist\QPopCV-v1.0.38.zip (XX.X MB)
```
If PyInstaller isn't on PATH, install it: `pip install pyinstaller` then retry.

- [ ] **Step 3: Verify ZIP structure**

```powershell
# List the top-level entries in the ZIP — should show only "QPopCV/"
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead("dist\QPopCV-v1.0.38.zip")
$zip.Entries | Select-Object -First 5 | ForEach-Object { $_.FullName }
$zip.Dispose()
```

Expected: entries like `QPopCV/QPopCV.exe`, `QPopCV/Qt6Core.dll`, `QPopCV/media/...`
The single top-level folder `QPopCV/` is required for `_find_source_root()` in `updater.py`.

- [ ] **Step 4: Commit**

```bash
git add build.ps1
git commit -m "build: add PowerShell build script for PyInstaller + release ZIP"
```

---

## Task 2: Create `docs/RELEASE.md` — Release Process Documentation

**Files:**
- Create: `docs/RELEASE.md`

- [ ] **Step 1: Write `docs/RELEASE.md`**

```markdown
# QPopCV Release Process

## Overview

Releases are published to GitHub as a ZIP asset containing the standalone Windows executable and all its dependencies. Users can install updates in-app; the update mechanism replaces files in-place so taskbar pins and user config survive every update.

---

## Pre-flight Checklist

Before every release:

- [ ] Bump `APP_VERSION` in `qpopcv/config.py` (e.g. `"1.0.38"` → `"1.0.39"`)
- [ ] Update `CLAUDE.md` — change "Current version" line to match
- [ ] Update `CLAUDE.md` — append the new version summary to "Active work order"
- [ ] Run tests: `python -m pytest` — all must pass
- [ ] Commit version bump: `git commit -m "chore: bump version to X.Y.Z"`

---

## Build

```powershell
.\build.ps1
```

This script:
1. Reads `APP_VERSION` from `qpopcv/config.py`
2. Compiles via `pyinstaller QPopCV.spec --clean --noconfirm`
3. Produces `dist\QPopCV-vX.Y.Z.zip`

Output ZIP structure:
```
QPopCV-vX.Y.Z.zip
└── QPopCV\
    ├── QPopCV.exe          ← the main executable (icon embedded)
    ├── Qt6Core.dll
    ├── Qt6WebEngineCore.dll
    ├── ... (PyInstaller dependencies)
    ├── config.json         ← shared defaults (from qpopcv/config.json)
    ├── media\
    │   └── icon\
    │       ├── icon_v2.ico
    │       └── QPopCV v2 logo.png
    ├── fonts\
    └── static\
        ├── index.html
        ├── style.css
        └── app.js
```

**NOT in the ZIP:** `config.local.json` (gitignored) — this is the user's personal settings file and is intentionally excluded from every release ZIP.

---

## Manual Test Before Publishing

1. Launch `dist\QPopCV\QPopCV.exe`
2. Verify the UI loads and the current version number is correct (shown in footer or About)
3. Enter a webhook URL and test the Discord ping
4. Close the app

---

## Publish to GitHub

### Using GitHub CLI (recommended)

```powershell
# Tag and push
git tag v1.0.38
git push origin v1.0.38

# Create release and upload the ZIP in one command
gh release create v1.0.38 "dist\QPopCV-v1.0.38.zip" `
  --title "v1.0.38" `
  --notes "Brief description of changes in this release."
```

### Manual via GitHub web

1. Go to https://github.com/Grymtrx/QPopCV/releases/new
2. Tag: `v1.0.38` (create new tag pointing at current commit)
3. Title: `v1.0.38`
4. Upload `dist\QPopCV-v1.0.38.zip` as a release asset
5. Publish

The asset filename **must** end in `.zip` — `updater.py:_select_download_url()` filters for `.zip` assets specifically.

---

## Verify the Update Check

After publishing:

1. Run an older version of QPopCV (e.g. build one locally with a lower version number)
2. The app should show "Update available: v1.0.38"
3. Click Install → verify the update.bat process runs, app restarts, new version shown

---

## How Updates Work (for reference)

When a user clicks "Install Update" in the app:

1. `updater.py:install_update()` downloads the release ZIP to a temp dir
2. Extracts to `%TEMP%\qpopcv_update_XXXXX\extracted\`
3. `_find_source_root()` detects the `QPopCV\` wrapper folder and returns it as source
4. Writes `qpopcv_update.bat` to the temp dir and launches it via `os.startfile()`
5. The app exits; the batch script waits, then runs:
   ```bat
   xcopy "%SRC%\*" "%DEST%\" /E /I /Y
   ```
   This copies all new files over the existing install directory.
6. Restarts `QPopCV.exe` from the same path, cleans up temp dir

**Taskbar pin stability:** The `.exe` is replaced in-place (same path, same filename). Windows taskbar pins are path-based, so the pin continues to launch the new exe without any user action. The updated exe has the new icon embedded, which Windows will pick up after the restart.

**Config persistence:** `config.local.json` is never included in the release ZIP (it is gitignored). The `xcopy` only copies files that are present in the ZIP, so `config.local.json` in the user's install folder is never touched. The user's webhook URL, Discord user ID, monitor selection, and AFK preference all survive every update.

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| `pyinstaller` not found | Not installed or not on PATH | `pip install pyinstaller` |
| ZIP missing `QPopCV\` wrapper | `build.ps1` used `dist\QPopCV\*` instead of `dist\QPopCV` | Use `Compress-Archive -Path "dist\QPopCV"` (no `\*`) |
| Update check finds no asset | Asset filename doesn't end in `.zip` | Rename/re-upload with `.zip` extension |
| `config.local.json` wiped on update | File was accidentally committed to repo and included in ZIP | Remove from git tracking: `git rm --cached qpopcv/config.local.json` |
| App icon on taskbar stays old | Windows icon cache | Right-click taskbar icon → Unpin, re-pin after update |
```

- [ ] **Step 2: Commit**

```bash
git add docs/RELEASE.md
git commit -m "docs: add release process documentation with update mechanics"
```

---

## Task 3: Create the `build-release` Skill

**Files:**
- Create: `C:\Users\Jesse\.claude\skills\build-release.md`

This skill encodes the release workflow so future Claude sessions can invoke it with the `Skill` tool. Use the `superpowers:writing-skills` skill to create it properly, or write it directly as shown.

- [ ] **Step 1: Invoke the writing-skills skill to create `build-release`**

In a future session, run:
> "Use the writing-skills skill to create a `build-release` skill for QPopCV"

The skill content to encode:

```markdown
---
name: build-release
description: Step-by-step workflow for building QPopCV from Python source to a GitHub release ZIP, including pre-flight checks, PyInstaller compilation, and publishing.
type: workflow
---

# QPopCV Build and Release Workflow

When the user asks to build a release, package the app, or publish a new version, follow this checklist exactly.

## Pre-flight

1. Confirm `APP_VERSION` in `qpopcv/config.py` has been bumped
2. Confirm `CLAUDE.md` "Current version" line matches
3. Run `python -m pytest` — all tests must pass before building

## Build

```powershell
.\build.ps1
```

Output: `dist\QPopCV-vX.Y.Z.zip`

Verify the ZIP exists and is > 50 MB (a smaller size indicates missing DLLs).

## Manual Test

Launch `dist\QPopCV\QPopCV.exe` and confirm it opens, shows the correct version, and the UI loads without errors.

## Publish

```powershell
git tag vX.Y.Z
git push origin vX.Y.Z
gh release create vX.Y.Z "dist\QPopCV-vX.Y.Z.zip" --title "vX.Y.Z" --notes "DESCRIPTION"
```

## Verify

After publishing, confirm the asset is visible on https://github.com/Grymtrx/QPopCV/releases and that its filename ends in `.zip`.

## Key facts

- `build.ps1` source: `D:\Git\QPopCV\build.ps1`
- Full release docs: `docs/RELEASE.md`
- Update mechanism: in-place xcopy via `qpopcv_update.bat` — taskbar pins survive, `config.local.json` is never overwritten
```

- [ ] **Step 2: Confirm the skill is registered in Claude settings**

After writing the skill file, verify it appears in the available skills list by checking Claude Code settings or starting a new session and checking the skill list.

---

## Self-Review

### Spec coverage
- [x] Build script (Python → exe → ZIP): Task 1
- [x] Taskbar pin stability (in-place replacement, same path): docs/RELEASE.md "How Updates Work"
- [x] Config persistence (config.local.json not in ZIP): docs/RELEASE.md "Config persistence"
- [x] Release documentation (checklist, commands): Task 2
- [x] Skill for build workflow: Task 3
- [x] Update mechanism explained clearly: Context section + RELEASE.md

### Placeholder scan
None found — all steps contain exact commands or file content.

### Type consistency
No cross-task type dependencies. Each task is standalone documentation/scripting.
