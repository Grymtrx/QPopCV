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

#### SEC-02 — No Webhook URL Format Validation
- **File:** `qpopcv/validators.py:8-34`
- **Detail:** `validate_discord_core` only checks that `webhook_url` is non-empty. Any string (including non-HTTPS or non-Discord URLs) will be accepted and POSTed to by the watcher.
- **Fix:** Add a regex or prefix check: `webhook_url.startswith("https://discord.com/api/webhooks/")`.

#### SEC-03 — Discord User ID Allows Any 18-Digit Number
- **File:** `qpopcv/validators.py:27`
- **Detail:** Validator accepts any 18-digit numeric string. Discord snowflake IDs are 18–19 digits and could be 17 digits for old accounts.
- **Fix:** Accept 17–19 digits: `user_id.isdigit() and 17 <= len(user_id) <= 19`.

#### SEC-04 — No Checksum/Signature Verification on Update ZIPs
- **File:** `qpopcv/updater.py:133-137`
- **Detail:** The downloaded release ZIP is extracted without verifying integrity. A compromised GitHub release asset could execute malicious code.
- **Fix:** GitHub releases expose an SHA-256 in their API (`assets[].digest`). Verify before extracting.

#### SEC-05 — Batch Script Path Injection Risk (Low Exploitability)
- **File:** `qpopcv/updater.py:261-291`
- **Detail:** `source_root`, `app_dir`, and `exe_path` are interpolated into an f-string batch script. Paths with special characters (e.g., `!`, `%`) could break or exploit the script.
- **Fix:** Paths are wrapped in quotes which handles spaces, but `!` and `%` in paths could expand unexpectedly with `ENABLEDELAYEDEXPANSION`. Sanitise or escape these characters, or use PowerShell instead of batch.

---

### Medium

#### SEC-06 — `load_config` Silent Exception Swallowing
- **File:** `qpopcv/config.py:31`
- **Detail:** `except Exception: pass` silently falls back to `DEFAULT_CONFIG` on any read or JSON parse error. The user gets no feedback that their config was lost.
- **Fix:** `except Exception: logger.warning("Failed to load config, using defaults: %s", exc)`.

---

## Bugs

#### BUG-01 — `subprocess` Imported Twice
- **File:** `qpopcv/updater.py:9,15`
- **Detail:** `import subprocess` appears on both line 9 and line 15. The second import is dead code.
- **Fix:** Remove the duplicate import on line 15.

#### BUG-02 — Watcher Has No Fallback Reference Images
- **File:** `qpopcv/watcher.py:253-254`
- **Detail:** `REFERENCE_IMG` is defined (lines 26-30) but never used. `_prepare_reference_images` only loads the user-provided image. If `reference_image_path` is empty or invalid, `_reference_images` is `[]` and detection is silently disabled with a `print()` — not a logger warning, not a dialog.
- **Impact:** User presses "Watch", gets no error, and the watcher runs but never detects anything.
- **Fix:** Surface an error to the user before starting the watcher if no reference image is loaded. Do not default to `REFERENCE_IMG` as user's screen resolution difference will cause detection mismatch.

#### BUG-03 — No `screenshot()` Failure Handling
- **File:** `qpopcv/watcher.py:198`
- **Detail:** `pyautogui.screenshot(region=self._region)` can return `None` or raise on some Windows configurations. This falls through to the generic `except Exception` handler which only prints a message and waits 2s — the watcher keeps "running" but does nothing useful.
- **Fix:** Add explicit `if screenshot is None: continue` check, or log at ERROR level so it's visible.

---

## Anti-Patterns / Code Quality

#### AP-01 — Mixed `print()` and `logging` Throughout Watcher
- **File:** `qpopcv/watcher.py:169,174,182,184,191,211,222,247,254`
- **Detail:** `_loop`, `_handle_detected_popup`, and `_prepare_reference_images` all use `print()` for operational output despite the module having a `logger`. This means output can't be redirected, filtered, or silenced via logging config.
- **Fix:** Replace all `print()` calls in `watcher.py` with `logger.info()` / `logger.warning()` / `logger.error()`.

#### AP-02 — `MEDIA_DIR` Frozen/Source Logic Duplicated
- **Files:** `qpopcv/watcher.py:18-23`, `qpopcv/updater.py:59-64`
- **Detail:** Both modules implement their own frozen-vs-source path detection. `config.py` already has `APP_DIR` doing this for one directory.
- **Fix:** Export `MEDIA_DIR` from `config.py` and import it in `watcher.py`.

#### AP-03 — `assert` Used as Control Flow in Production Code
- **File:** `qpopcv/app_ui.py:466`
- **Detail:** `assert self._update_info is not None` — asserts are stripped in optimised Python (`python -O`). This should be a proper `if` guard.
- **Fix:** `if self._update_info is None: return`.

#### AP-04 — `os._exit(0)` Called Without Cleanup
- **File:** `qpopcv/app_ui.py:496`
- **Detail:** `os._exit(0)` bypasses Python cleanup (no `finally` blocks, no `atexit` handlers, no `__del__`). While intentional for the update case, it could leave the watcher thread without a clean shutdown if threading cleanup matters.
- **Fix:** This is acceptable for the update use case. Document with a comment explaining why `os._exit` is chosen over `sys.exit`.

#### AP-05 — Bare `except Exception` in Update Check Loses Error Context
- **File:** `qpopcv/updater.py:105`
- **Detail:** `except Exception:` with no logging means update check failures are completely invisible. `app_ui.py` handles this gracefully in the UI, but the underlying error (network timeout, SSL, JSON parse) is never recorded anywhere.
- **Fix:** Add `logger.debug("Update check failed", exc_info=True)` inside the except.

#### AP-06 — `import os` Inside a Method
- **File:** `qpopcv/app_ui.py:489`
- **Detail:** `import os` appears inside `_restart_after_update`. This works but is unconventional and slower than a module-level import.
- **Fix:** Move `import os` to the top of the file.

---

## Missing Features / Gaps

#### GAP-01 — Zero Automated Tests
- **Detail:** The `tests/` directory contains only manual utility scripts. There is no pytest setup, no unit tests, no mocks.
- **Impact:** Every change is manually tested. Regressions are hard to catch.
- **Suggested test targets:** `validators.py` (pure functions), `updater._normalize_version`, `updater._is_newer_version`, `watcher._compute_top_center_region`, config load/save round-trip.

#### GAP-02 — No Log File Output
- **Detail:** Logging goes only to console (stdout). If the app is run from a `.exe` with no terminal, all log output is lost.
- **Fix:** Add a `logging.FileHandler` pointing to `APP_DIR / "qpopcv.log"` with a rotating handler.

#### GAP-03 — Multi-Monitor Support
- **Detail:** `pyautogui.size()` returns the primary monitor's resolution. On multi-monitor setups, the game may be on a secondary display, and the computed region will be wrong.
- **Fix:** Let the user manually configure the watch region, or detect the game window position.

#### GAP-04 — No Rate Limiting on Test Discord Button
- **Detail:** The 15-second throttle applies to the watcher, and `_check_test_throttle` reuses `THROTTLE_SECONDS`. However the throttle is per-session (resets on restart) and uses `_last_test_time` which is independent of watcher state — so a user can send a test message immediately after a detection notification.
- **Impact:** Low — mostly a cosmetic inconsistency.

#### GAP-05 — `confidence` Not Exposed in UI
- **Detail:** The `confidence` config key (default `0.6`) controls template match sensitivity but has no UI control. Users with unusual screen scaling or DPI may need to adjust it.
- **Fix:** Add a slider or numeric entry for confidence in the settings area.

#### GAP-06 — `check_interval` Not Exposed in UI
- **Detail:** Same as above for `check_interval` (default `0.15s` = ~6.7 FPS capture). Power users may want to reduce CPU usage.

#### GAP-07 — `opencv-python` in Requirements but Not Used
- **File:** `requirements.txt`
- **Detail:** `opencv-python` is listed as a dependency but is never imported in any source file.
- **Fix:** Remove from `requirements.txt`. This reduces install size (~40MB) and avoids false dependency expectations.

---

## Suggested Improvement Roadmap

Priority order for a future Claude session:

1. **SEC-01** — Remove hardcoded webhook (security critical, 5 min fix)
2. **BUG-02** — Surface detection disabled state to user (UX critical)
3. **AP-01** — Replace all `print()` in watcher with `logger` calls (code quality)
4. **GAP-07** — Remove unused `opencv-python` from requirements
5. **SEC-02** — Add webhook URL domain validation
6. **GAP-01** — Add pytest + a few unit tests for pure functions
7. **GAP-02** — Add rotating file log handler
8. **AP-02** — Consolidate `MEDIA_DIR` into `config.py`
9. **GAP-03** — Multi-monitor region support
10. **GAP-05/06** — Expose confidence + interval in UI
