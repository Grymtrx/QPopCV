# Codebase Size Reduction & Repo Cleanup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove ~170 MB of build artifacts from git, delete ~1.7 GB of local cruft, trim unused files, add PyInstaller excludes, and document expected build sizes.

**Architecture:** Pure cleanup — no behavioral changes. Git tracking removals, file deletions, .gitignore hardening, .spec excludes, doc updates, version bump.

**Tech Stack:** Git, PyInstaller (.spec), Python (pytest), PowerShell (build.ps1)

---

### Task 1: Update .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add missing ignore patterns**

Add these entries to `.gitignore` under the appropriate sections:

Under `# Build artifacts / distributors`:
```
# PyInstaller runtime (regenerated every build)
qpopcv/_internal/
```

Under `# Logs & runtime data`:
```
qpopcv/*.log
```

The existing `*.exe`, `*.spec`, `build/`, `dist/`, and `metrics.json` patterns already cover the other items. No changes needed for those.

- [ ] **Step 2: Verify ignore patterns work**

Run:
```bash
git status --ignored --short | grep '_internal'
```
Expected: `_internal/` shows as `!!` (ignored)

---

### Task 2: Remove build artifacts from git tracking

**Files:**
- Untrack: `qpopcv/_internal/` (982 files), `qpopcv/theme.py`, `qpopcv/media/icon/icon.ico`, `qpopcv/media/v1.1.0.png`, `q.png`, `expirements/`

- [ ] **Step 1: Untrack _internal/ from git (keep local copy)**

Run:
```bash
git rm -r --cached qpopcv/_internal/
```
Expected: `rm 'qpopcv/_internal/...'` for 982 files. The files remain on disk but git stops tracking them.

- [ ] **Step 2: Delete unused tracked files from git AND disk**

Run:
```bash
git rm qpopcv/theme.py
git rm qpopcv/media/icon/icon.ico
git rm qpopcv/media/v1.1.0.png
git rm q.png
git rm -r expirements/
```

- [ ] **Step 3: Commit the git cleanup**

Run:
```bash
git add .gitignore
git commit -m "chore: remove build artifacts from tracking, delete unused files

- Untrack qpopcv/_internal/ (170 MB PyInstaller output)
- Delete theme.py (deprecated CustomTkinter artifact)
- Delete icon.ico (replaced by icon_v2.ico)
- Delete v1.1.0.png (unreferenced screenshot)
- Delete q.png (unreferenced root image)
- Delete expirements/ (old HTML prototypes)
- Update .gitignore to prevent re-tracking"
```

---

### Task 3: Delete local build artifacts (~1.7 GB)

- [ ] **Step 1: Delete regenerable directories and files**

Run (from repo root):
```bash
rm -rf dist/
rm -rf build/
rm -rf qpopcv/_internal/
rm -f qpopcv/QPopCV.exe
rm -rf __pycache__/
rm -rf .pytest_cache/
rm -rf qpopcv/__pycache__/
rm -rf tests/__pycache__/
```

- [ ] **Step 2: Verify protected files still exist**

Run:
```bash
test -d .venv && echo ".venv OK"
test -f qpopcv/config.local.json && echo "config.local.json OK"
test -f qpopcv/metrics.json && echo "metrics.json OK"
test -f QPopCV.spec && echo "QPopCV.spec OK"
```
Expected: All four print OK.

---

### Task 4: Clean up conftest.py

**Files:**
- Modify: `conftest.py`

- [ ] **Step 1: Remove the dead CustomTkinter stub**

In `conftest.py`, remove the `_stub_customtkinter()` function (lines 53-60) and its call (line 66).

Before:
```python
def _stub_customtkinter():
    ctk = MagicMock()
    ctk.CTk = MagicMock
    ctk.CTkFrame = MagicMock
    ctk.CTkLabel = MagicMock
    ctk.CTkEntry = MagicMock
    ctk.CTkButton = MagicMock
    ctk.StringVar = MagicMock
    sys.modules.setdefault("customtkinter", ctk)


_stub_tkinter()
_stub_pyautogui()
_stub_customtkinter()
```

After:
```python
_stub_tkinter()
_stub_pyautogui()
```

- [ ] **Step 2: Run tests to verify nothing breaks**

Run:
```bash
python -m pytest -v
```
Expected: All tests pass.

- [ ] **Step 3: Commit**

Run:
```bash
git add conftest.py
git commit -m "chore: remove dead CustomTkinter stub from conftest.py"
```

---

### Task 5: Add PyInstaller excludes to .spec

**Files:**
- Modify: `QPopCV.spec`

- [ ] **Step 1: Add excludes list**

In `QPopCV.spec`, change the `excludes` parameter in the `Analysis()` call from:
```python
    excludes=[],
```
to:
```python
    excludes=[
        'tkinter', '_tkinter',
        'unittest', 'pydoc', 'doctest',
        'xml', 'xmlrpc',
        'sqlite3',
    ],
```

Note: `multiprocessing` is excluded from this list because `pyscreeze` (used by `pyautogui`) imports it internally. `tcl`/`tk` are excluded implicitly by excluding `tkinter`.

- [ ] **Step 2: Commit**

Run:
```bash
git add QPopCV.spec
git commit -m "chore: add PyInstaller excludes to reduce exe size

Exclude unused stdlib modules: tkinter, unittest, pydoc, doctest, xml, xmlrpc, sqlite3"
```

---

### Task 6: Bump version to 1.2.4

**Files:**
- Modify: `qpopcv/config.py:19`
- Modify: `CLAUDE.md:25`

- [ ] **Step 1: Update APP_VERSION**

In `qpopcv/config.py`, change:
```python
APP_VERSION = "1.2.3"
```
to:
```python
APP_VERSION = "1.2.4"
```

- [ ] **Step 2: Update CLAUDE.md version line**

In `CLAUDE.md`, change:
```
Increment the patch version (`APP_VERSION` in `qpopcv/config.py`) on every code change. Current version: `1.2.3`.
```
to:
```
Increment the patch version (`APP_VERSION` in `qpopcv/config.py`) on every code change. Current version: `1.2.4`.
```

- [ ] **Step 3: Append to active work order in CLAUDE.md**

At the end of the "Active work order" line, append:
```
 Codebase cleanup — removed 170 MB build artifacts from git, deleted unused files, added PyInstaller excludes, updated .gitignore (v1.2.4).
```

- [ ] **Step 4: Run tests**

Run:
```bash
python -m pytest -v
```
Expected: All tests pass.

- [ ] **Step 5: Commit**

Run:
```bash
git add qpopcv/config.py CLAUDE.md
git commit -m "chore: bump version to 1.2.4"
```

---

### Task 7: Update build-release skill and RELEASE.md with file size info

**Files:**
- Modify: `C:\Users\Jesse\.claude\skills\build-release\SKILL.md`
- Modify: `docs/RELEASE.md`

- [ ] **Step 1: Add expected sizes to the build-release skill**

In `C:\Users\Jesse\.claude\skills\build-release\SKILL.md`, add a new section after the `## Build` section:

```markdown
## Expected sizes

After building, verify the output sizes are in the expected range:

| Artifact | Expected size |
|----------|--------------|
| `dist\QPopCV\` (uncompressed) | ~500-600 MB |
| `dist\QPopCV-vX.Y.Z.zip` | ~250-270 MB |
| `dist\QPopCV\QPopCV.exe` | ~7-8 MB |

If the ZIP is significantly larger than expected, check for accidentally bundled dependencies (e.g. test frameworks, unused Qt modules). If significantly smaller, verify all required DLLs and assets are present.
```

Note: The exact values should be updated after the first post-cleanup build. The ranges above are estimates based on v1.2.x builds.

- [ ] **Step 2: Add expected sizes to RELEASE.md**

In `docs/RELEASE.md`, after the "Output ZIP structure" code block (after line 50), add:

```markdown
**Expected output sizes (v1.2.x):**

| Artifact | Expected size |
|----------|--------------|
| `dist\QPopCV\` (uncompressed folder) | ~500-600 MB |
| `dist\QPopCV-vX.Y.Z.zip` | ~250-270 MB |

If sizes differ significantly from these ranges, investigate before publishing.
```

- [ ] **Step 3: Commit**

Run:
```bash
git add docs/RELEASE.md
git commit -m "docs: add expected build sizes to release workflow"
```

Note: The skill file is outside the repo, so it won't be part of the git commit.

---

### Task 8: Final verification

- [ ] **Step 1: Run full test suite**

Run:
```bash
python -m pytest -v
```
Expected: All tests pass.

- [ ] **Step 2: Verify repo is clean**

Run:
```bash
git status
```
Expected: No unexpected untracked or modified files. `qpopcv/_internal/` should NOT appear (gitignored). `config.local.json`, `metrics.json`, `QPopCV.spec` should show as ignored or not listed.

- [ ] **Step 3: Verify disk savings**

Run:
```bash
du -sh .git/
```
Note the size. On next clone, the repo will be ~170 MB lighter (the .git folder on this machine still contains the old objects until garbage collection or a fresh clone).
