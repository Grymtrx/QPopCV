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
    │       ├── icon.ico
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
