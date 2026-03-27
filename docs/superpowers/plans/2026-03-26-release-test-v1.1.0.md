# v1.1.0 Release Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bump to v1.1.0, build the release, publish to GitHub, then build a test .exe at v1.0.43 and verify the full in-app update flow (detect → download → update.bat → restart).

**Architecture:** Standard release pipeline — version bump across 3 files, PyInstaller build via `build.ps1`, GitHub release via `gh`, then a second build at a lower version to exercise the updater.

**Tech Stack:** Python 3.14, PyInstaller, PowerShell, GitHub CLI (`gh`)

---

## Task 1: Bump version to 1.1.0

**Files:**
- Modify: `qpopcv/config.py:19` — change `APP_VERSION`
- Modify: `CLAUDE.md:22` — change "Current version" line
- Modify: `CLAUDE.md:25` — append v1.1.0 to work order
- Modify: `docs/RELEASE.md` — update all example version references to v1.1.0

- [ ] **Step 1: Update `APP_VERSION` in `qpopcv/config.py`**

Change line 19 from:
```python
APP_VERSION = "1.0.43"
```
to:
```python
APP_VERSION = "1.1.0"
```

- [ ] **Step 2: Update `CLAUDE.md` version line**

Change line 22 from:
```
Increment the patch version (`APP_VERSION` in `qpopcv/config.py`) on every code change. Current version: `1.0.43`.
```
to:
```
Increment the patch version (`APP_VERSION` in `qpopcv/config.py`) on every code change. Current version: `1.1.0`.
```

- [ ] **Step 3: Append v1.1.0 to `CLAUDE.md` work order**

At the end of the "Active work order" paragraph on line 25, append:
```
v1.1.0 release — first official release with full update flow testing.
```

- [ ] **Step 4: Update `docs/RELEASE.md` version references**

Replace all `v1.0.38` references with `v1.1.0` in:
- Line 13: pre-flight example `"1.0.38" → "1.0.39"` becomes `"1.0.43" → "1.1.0"`
- Line 67: "Replace `v1.0.38`..." becomes "Replace `v1.1.0`..."
- Lines 72-79: all `v1.0.38` in CLI examples → `v1.1.0`
- Lines 83-88: all `v1.0.38` in manual examples → `v1.1.0`
- Lines 99, 103: update check section references → `v1.1.0`

- [ ] **Step 5: Run tests**

Run: `python -m pytest`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add qpopcv/config.py CLAUDE.md docs/RELEASE.md
git commit -m "chore: bump version to 1.1.0"
```

---

## Task 2: Build the v1.1.0 release ZIP

**Files:**
- Uses: `build.ps1`
- Output: `dist\QPopCV-v1.1.0.zip`

- [ ] **Step 1: Run the build script**

```powershell
.\build.ps1
```

Expected output ends with:
```
[build] Done: dist\QPopCV-v1.1.0.zip (XX.X MB)
```

- [ ] **Step 2: Verify the .exe launches and shows v1.1.0**

Launch `dist\QPopCV\QPopCV.exe` manually. Verify:
- UI loads without errors
- Footer shows version `1.1.0`

Close the app after verifying.

---

## Task 3: Publish v1.1.0 to GitHub

- [ ] **Step 1: Tag and push**

```powershell
git tag v1.1.0
git push origin main
git push origin v1.1.0
```

- [ ] **Step 2: Create the GitHub release**

```powershell
gh release create v1.1.0 "dist\QPopCV-v1.1.0.zip" --title "v1.1.0" --notes "First official release. PyQt6 + QWebEngineView UI, Discord webhook notifications, AFK timer, in-app auto-updater."
```

- [ ] **Step 3: Verify the release is live**

```powershell
gh release view v1.1.0
```

Confirm the `.zip` asset is listed and the release is not marked as draft or pre-release.

---

## Task 4: Build a test .exe at v1.0.43

**Files:**
- Temporarily modify: `qpopcv/config.py:19`

- [ ] **Step 1: Temporarily set version to 1.0.43**

Change line 19 of `qpopcv/config.py` to:
```python
APP_VERSION = "1.0.43"
```

Do NOT commit this change.

- [ ] **Step 2: Build the test .exe**

```powershell
.\build.ps1
```

This overwrites `dist\QPopCV\QPopCV.exe` with a version that reports `1.0.43`.

- [ ] **Step 3: Revert config.py back to 1.1.0**

Change line 19 of `qpopcv/config.py` back to:
```python
APP_VERSION = "1.1.0"
```

Verify no uncommitted changes remain: `git diff qpopcv/config.py` should show no diff.

---

## Task 5: Test the update flow (manual — user performs these steps)

- [ ] **Step 1: Launch the test .exe**

Launch `dist\QPopCV\QPopCV.exe`. It will report version `1.0.43`.

- [ ] **Step 2: Verify update detection**

Wait a few seconds for the SSE event. The footer should show:
```
Update available: 1.1.0
```
The text should be clickable (underlined or highlighted).

- [ ] **Step 3: Click the update text**

A confirm dialog appears:
> "An update is available. Download and install now? The app will restart automatically."

Click OK.

- [ ] **Step 4: Observe the update process**

Expected sequence:
1. Text changes to "Downloading..."
2. A cmd window opens running `qpopcv_update.bat`
3. The app window closes
4. The batch script copies files
5. The app restarts automatically

- [ ] **Step 5: Verify the updated app**

After restart, verify:
- App launches and UI loads
- Footer shows version `1.1.0`
- `config.local.json` still exists (if it existed before) with your settings intact

- [ ] **Step 6: Verify taskbar pin (if applicable)**

If the app is pinned to the taskbar, click the pin. It should launch the updated v1.1.0 app.

---

## Rollback Plan

If anything fails after publishing, run:

```powershell
gh release delete v1.1.0 --yes
git push --delete origin v1.1.0
git tag -d v1.1.0
```

Then diagnose and fix the issue before re-attempting.

---

## Self-Review

### Spec coverage
- [x] Version bump across config.py, CLAUDE.md, RELEASE.md: Task 1
- [x] Build the release ZIP: Task 2
- [x] Publish to GitHub as a real release: Task 3
- [x] Build test .exe with lower version: Task 4
- [x] Test update detection, download, update.bat, restart: Task 5
- [x] Rollback plan: documented
- [x] Config persistence verification: Task 5 Step 5
- [x] Taskbar pin verification: Task 5 Step 6

### Placeholder scan
None found — all steps contain exact commands and expected outputs.

### Type consistency
Version strings are consistent: `1.0.43` for current/test, `1.1.0` for target, throughout.
