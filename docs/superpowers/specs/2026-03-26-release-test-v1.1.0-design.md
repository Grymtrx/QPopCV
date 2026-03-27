# v1.1.0 Release Test Plan

## Goal

Validate the full release-and-update cycle end-to-end before committing to v1.1.0 as the official release. This tests the build pipeline, GitHub release publishing, in-app update detection, ZIP download, `update.bat` execution, and app restart.

## Context

- Current `APP_VERSION`: `1.0.43`
- Last published GitHub release: `v1.0.4`
- Target release version: `1.1.0`
- Update mechanism: `updater.py` checks `GET /repos/Grymtrx/QPopCV/releases/latest`, compares versions, downloads `.zip` asset, extracts, and runs `update.bat` (frozen .exe path)

## Approach

Publish `v1.1.0` as a real GitHub release (the `/releases/latest` API endpoint skips drafts and pre-releases). Then build a test `.exe` with a lower version to trigger the update flow.

---

## Phase 1 — Prepare the release

1. Bump `APP_VERSION` in `qpopcv/config.py` from `"1.0.43"` to `"1.1.0"`
2. Update `CLAUDE.md`:
   - Change "Current version" to `1.1.0`
   - Append v1.1.0 summary to "Active work order"
3. Update `RELEASE.md` example commands to reference `v1.1.0`
4. Run `python -m pytest` — all tests must pass
5. Commit: `"chore: bump version to 1.1.0"`
6. Build: `.\build.ps1` produces `dist\QPopCV-v1.1.0.zip`

## Phase 2 — Publish to GitHub

7. Tag and push: `git tag v1.1.0 && git push origin v1.1.0`
8. Create release: `gh release create v1.1.0 "dist\QPopCV-v1.1.0.zip" --title "v1.1.0" --notes "..."`
   - Published as a **full release** (not draft, not pre-release)

## Phase 3 — Build a test .exe

9. Temporarily set `APP_VERSION = "1.0.43"` in `config.py` (do NOT commit)
10. Run `.\build.ps1` — produces a `.exe` that reports version `1.0.43`
11. Revert `config.py` back to `"1.1.0"`

## Phase 4 — Test the update flow

12. Launch the `1.0.43` test `.exe` from `dist\QPopCV\QPopCV.exe`
13. Verify footer shows "Update available: 1.1.0" (clickable)
14. Click the update text -> confirm dialog -> "Downloading..."
15. Verify:
    - ZIP downloads successfully
    - `update.bat` spawns in a cmd window
    - App closes
    - Files are copied from extracted ZIP to the app directory
    - App restarts automatically
16. Verify restarted app shows version `1.1.0` in footer
17. Verify taskbar pin still works (same exe path)

## Rollback Plan

If anything fails after publishing:

```powershell
gh release delete v1.1.0 --yes
git push --delete origin v1.1.0
git tag -d v1.1.0
```

Then fix the issue and re-attempt.

## Success Criteria

- [ ] Test `.exe` (v1.0.43) detects v1.1.0 as available
- [ ] Update text becomes clickable in the UI
- [ ] Download completes without error
- [ ] `update.bat` runs, replaces files, restarts app
- [ ] Restarted app shows v1.1.0
- [ ] `config.local.json` (if present) survives the update
- [ ] Taskbar pin still launches the app
