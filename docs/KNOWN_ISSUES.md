# QPopCV — Known Issues & Tech Debt

> **Purpose of this document:** Prioritised list of security issues, bugs, anti-patterns, and missing features. Use this before starting any new work to understand existing liabilities.

---

## Security Issues

### CRITICAL 

#### SEC-01 — Hardcoded Discord Webhook URL in Source Control    (DO NOT FIX THIS ISSUE WITHOUT EXPLICIT APPROVAL FROM DEVELOPER)
- **Files:** `qpopcv/config.py:16`, `qpopcv/config.json:2`
- **Detail:** A real, live Discord webhook URL is committed to the repository as the `DEFAULT_CONFIG` value. Anyone with repo access (or who clones the repo) can POST messages to this webhook indefinitely.
- **Impact:** Unwanted messages in your Discord channel; webhook spamming; social engineering via your channel.
- **Fix:**
  1. Regenerate the webhook in Discord immediately (the exposed one should be considered compromised).
  2. Set `DEFAULT_CONFIG["webhook_url"]` to `""`.
  3. Clear `config.json`'s `webhook_url` to `""` and add `config.json` to `.gitignore` or exclude it from commits.

---

### High

#### ~~SEC-02 — No Webhook URL Format Validation~~ ✅ Fixed in 1.0.7
- `validate_discord_core` now rejects any URL that does not start with `https://discord.com/api/webhooks/`.

#### ~~SEC-03 — Discord User ID Allows Any 18-Digit Number~~ ✅ Fixed in 1.0.8
- Validator now accepts 17–19 digit IDs to cover old accounts and 19-digit snowflakes.

#### ~~SEC-04 — No Checksum/Signature Verification on Update ZIPs~~ ✅ Fixed in 1.0.39
- `UpdateInfo` now carries `asset_digest` (populated from `assets[].digest` in the GitHub API). `install_update` calls `_verify_checksum()` before extracting if a digest is present.

#### ~~SEC-05 — Batch Script Path Injection Risk (Low Exploitability)~~ ✅ Fixed in 1.0.8
- Replaced `ENABLEDELAYEDEXPANSION` with `DISABLEDELAYEDEXPANSION` so `!` characters in paths are never expanded.

---

### Medium

#### ~~SEC-06 — `load_config` Silent Exception Swallowing~~ ✅ Fixed in 1.0.9
- `except Exception as exc` now logs `logger.warning("Failed to load config, using defaults: %s", exc)` instead of silently passing.

---

## Bugs

#### ~~BUG-01 — `subprocess` Imported Twice~~ ✅ Fixed in 1.0.8
- Removed duplicate `import subprocess` from `updater.py`.

#### ~~BUG-02 — Watcher Has No Fallback Reference Images~~ ✅ Fixed in 1.0.5
- `_start_watch()` in `app_ui.py` now calls `validate_reference_image()` and shows an error dialog before starting the watcher if no valid image is set.
- Silent `print()` in `_prepare_reference_images` replaced with `logger.warning()`.

#### ~~BUG-03 — No `screenshot()` Failure Handling~~ ✅ Fixed in 1.0.8
- Added explicit `if screenshot is None: logger.error(...); continue` guard in `watcher.py`.

---

## Anti-Patterns / Code Quality

#### ~~AP-01 — Mixed `print()` and `logging` Throughout Watcher~~ ✅ Fixed in 1.0.6
- All `print()` calls in `watcher.py` replaced with appropriate `logger.info()` / `logger.debug()` / `logger.error()` calls.

#### ~~AP-02 — `MEDIA_DIR` Frozen/Source Logic Duplicated~~ ✅ Fixed in 1.0.9
- `MEDIA_DIR` (with `_MEIPASS` frozen support) now lives in `config.py`; `watcher.py` imports it from there.

#### ~~AP-03 — `assert` Used as Control Flow in Production Code~~ ✅ Fixed in 1.0.24
- `api.py:install_update` uses `if not self._update_info or not self._update_info.available: return`. The assert was removed when `app_ui.py` was rewritten for the PyQt6 migration.

#### ~~AP-04 — `os._exit(0)` Called Without Cleanup~~ ✅ Fixed in 1.0.24
- Removed during PyQt6 migration. Update install now calls `self._quit_fn()` which triggers a clean Qt window close via `QMainWindow.close()`.

#### ~~AP-05 — Bare `except Exception` in Update Check Loses Error Context~~ ✅ Fixed in 1.0.39
- Added `logger.debug("Update check failed", exc_info=True)` to the except block in `updater.py:check_for_update`.

#### ~~AP-06 — `import os` Inside a Method~~ ✅ Fixed in 1.0.24
- `_restart_after_update` was removed during the PyQt6 migration. In the current codebase `os` is imported at module level in `updater.py` (the only file that calls `os.startfile`).

---

## Missing Features / Gaps

#### ~~GAP-01 — Zero Automated Tests~~ ✅ Fixed in 1.0.7
- 93 pytest tests across `test_validators.py`, `test_config.py`, `test_updater.py`, and `test_watcher.py`. Run with: `python -m pytest`.

#### ~~GAP-02 — No Log File Output~~ ✅ Fixed in 1.0.10
- `main.py` now attaches a `RotatingFileHandler` (1 MB, 3 backups) writing to `APP_DIR / "qpopcv.log"` alongside the console handler.

#### ~~GAP-03 — Multi-Monitor Support~~ ✅ Fixed in 1.0.12
- Added a "Game Monitor" dropdown to the UI. `monitor_utils.get_monitors()` enumerates monitors via stdlib `ctypes` (no new dependencies); primary monitor is first. Config stores `monitor_index` (int). `QPopWatcher` uses `compute_top_center_region(monitor)` to derive the watch region for the selected display.

#### ~~UI/UX Redesign~~ ✅ Done in 1.0.22
- Window widened 420→480px; card is pure white; section headers in sky-blue (`TEXT_SECTION`).
- "Test" button moved from action bar into Discord section header (contextually co-located).
- Status pill moved from bottom row into action bar (centered between Save and Watch).
- Browse button changed from `⊞` to `...`; footer mobile hint de-capped and made readable at 9px.
- Stale tests in `test_config.py` and `test_watcher.py` fixed to match current API (`USER_CONFIG_PATH`, `reference_image_paths`).

#### ~~GAP-04 — No Rate Limiting on Test Discord Button~~ ✅ Fixed in 1.0.10
- `TEST_THROTTLE_SECONDS = 1` introduced in `app_ui.py`; `_check_test_throttle` now uses it instead of the watcher's 15s `THROTTLE_SECONDS`.

#### ~~GAP-08 — AFK Timer `_afk_timer` Assignment Has CPython-Only Thread Safety~~ ✅ Documented
- A comment was added to `api.py:_send_afk_notification` explaining the GIL guarantee. If free-threaded Python is ever used, wrap `_afk_timer` access in a `threading.Lock`.


#### ~~GAP-07 — `opencv-python` in Requirements but Not Used~~ ✅ Fixed in 1.0.7
- Removed from `requirements.txt` and `pyproject.toml`.

---

## Suggested Improvement Roadmap

Priority order for a future Claude session:

1. **SEC-01** — Remove hardcoded webhook (security critical, 5 min fix)
2. ~~**BUG-02** — Surface detection disabled state to user (UX critical)~~ ✅ Fixed in 1.0.5
3. ~~**AP-01** — Replace all `print()` in watcher with `logger` calls (code quality)~~ ✅ Fixed in 1.0.6
4. ~~**GAP-07** — Remove unused `opencv-python` from requirements~~ ✅ Fixed in 1.0.7
5. ~~**SEC-02** — Add webhook URL domain validation~~ ✅ Fixed in 1.0.7
6. ~~**GAP-01** — Add pytest + a few unit tests for pure functions~~ ✅ Fixed in 1.0.7
7. ~~**SEC-03** — Broaden user ID digit range~~ ✅ Fixed in 1.0.8
8. ~~**SEC-05** — Batch script delayed expansion risk~~ ✅ Fixed in 1.0.8
9. ~~**BUG-01** — Duplicate `subprocess` import~~ ✅ Fixed in 1.0.8
10. ~~**BUG-03** — No `screenshot()` None guard~~ ✅ Fixed in 1.0.8
11. ~~**SEC-06** — `load_config` silent exception swallowing~~ ✅ Fixed in 1.0.9
12. ~~**AP-02** — Consolidate `MEDIA_DIR` into `config.py`~~ ✅ Fixed in 1.0.9
13. ~~**GAP-02** — Add rotating file log handler~~ ✅ Fixed in 1.0.10
14. ~~**GAP-04** — Test button reused watcher throttle~~ ✅ Fixed in 1.0.10
13. ~~**GAP-03** — Multi-monitor region support~~ ✅ Fixed in 1.0.12
14. ~~**UI/UX Redesign**~~ ✅ Done in 1.0.22
15. ~~**AFK Tab**~~ ✅ Done in 1.0.38 — 28-min Discord ping with @mention; `threading.Timer` armed on Watch start, cancelled on Stop
16. ~~**AP-05**~~ ✅ Fixed in 1.0.39 — Log update check failures
17. ~~**SEC-04**~~ ✅ Fixed in 1.0.39 — SHA-256 checksum verification on downloaded ZIPs
