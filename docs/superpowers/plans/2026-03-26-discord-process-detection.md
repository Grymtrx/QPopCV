# Discord Process Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect whether Discord.exe is running when the user clicks Watch, and if so show an inline warning with options to kill Discord or continue anyway — so users don't receive notifications on their PC instead of their phone.

**Architecture:** A module-level `_is_discord_running()` helper and `Api.kill_discord()` method are added to `api.py` using `psutil`. The `start_watch()` method gains a `skip_discord_check` flag. The frontend's `doStartWatch()` handles the new `discord_running` response by showing an inline warning banner with Kill/Continue buttons above the Watch button.

**Tech Stack:** `psutil` (new dep), existing PyQt6/HTTP/SSE stack, vanilla JS frontend

---

## File Map

| File | Change |
|------|--------|
| `requirements.txt` | Add `psutil` |
| `qpopcv/api.py` | Import `psutil`; add `_is_discord_running()`; add `kill_discord()` to `Api`; add `skip_discord_check` param to `start_watch()` |
| `qpopcv/app_ui.py` | Register `/api/kill_discord` route in `do_POST` |
| `qpopcv/static/index.html` | Add `#discord-warn` banner element in footer between save-row and watch-btn |
| `qpopcv/static/app.js` | Add DOM refs; handle `discord_running` in `doStartWatch()`; wire Kill/Continue buttons |
| `qpopcv/static/style.css` | Add `.discord-warn` styles |
| `qpopcv/config.py` | Bump `APP_VERSION` to `1.0.40` |
| `tests/test_api_discord_check.py` | New test file for all Discord detection logic |

---

## Task 1: Add psutil dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add psutil to requirements.txt**

Open `requirements.txt`. It currently reads:
```
PyQt6>=6.5
PyQt6-WebEngine>=6.5
pyautogui
opencv-python
pillow
requests
pytest
```

Change it to:
```
PyQt6>=6.5
PyQt6-WebEngine>=6.5
pyautogui
opencv-python
pillow
requests
psutil
pytest
```

- [ ] **Step 2: Verify psutil is importable**

Run:
```bash
python -c "import psutil; print(psutil.__version__)"
```
Expected: prints a version string (e.g. `6.x.x`). psutil ships as a transitive dep already; this just makes it explicit.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "build: add psutil to requirements for Discord process detection"
```

---

## Task 2: Write tests for Discord detection backend

**Files:**
- Create: `tests/test_api_discord_check.py`

- [ ] **Step 1: Create the test file**

Create `tests/test_api_discord_check.py` with this content:

```python
"""Tests for Discord process detection in qpopcv/api.py."""
import pytest
from unittest.mock import patch, MagicMock

from qpopcv.api import Api, _is_discord_running

VALID_WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/token"
VALID_USER_ID = "123456789012345678"


def make_config(**overrides):
    base = {
        "webhook_url": VALID_WEBHOOK,
        "user_id": VALID_USER_ID,
        "reference_image_paths": [],
        "monitor_index": 0,
        "afk_notify": False,
    }
    base.update(overrides)
    return base


def make_api(config=None):
    if config is None:
        config = make_config()
    return Api(config, push_event=lambda t, d: None)


# ── _is_discord_running ────────────────────────────────────────────────────

class TestIsDiscordRunning:

    @patch("qpopcv.api.psutil.process_iter")
    def test_returns_true_when_discord_running(self, mock_iter):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "Discord.exe"
        mock_iter.return_value = [mock_proc]
        assert _is_discord_running() is True

    @patch("qpopcv.api.psutil.process_iter")
    def test_returns_false_when_discord_not_running(self, mock_iter):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "chrome.exe"
        mock_iter.return_value = [mock_proc]
        assert _is_discord_running() is False

    @patch("qpopcv.api.psutil.process_iter")
    def test_case_insensitive_match(self, mock_iter):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "DISCORD.EXE"
        mock_iter.return_value = [mock_proc]
        assert _is_discord_running() is True

    @patch("qpopcv.api.psutil.process_iter")
    def test_returns_false_when_no_processes(self, mock_iter):
        mock_iter.return_value = []
        assert _is_discord_running() is False


# ── kill_discord ──────────────────────────────────────────────────────────

class TestKillDiscord:

    @patch("qpopcv.api.psutil.process_iter")
    def test_terminates_discord_processes(self, mock_iter):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "Discord.exe"
        mock_iter.return_value = [mock_proc]
        api = make_api()
        result = api.kill_discord()
        mock_proc.terminate.assert_called_once()
        assert result["ok"] is True

    @patch("qpopcv.api.psutil.process_iter")
    def test_skips_non_discord_processes(self, mock_iter):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "chrome.exe"
        mock_iter.return_value = [mock_proc]
        api = make_api()
        result = api.kill_discord()
        mock_proc.terminate.assert_not_called()
        assert result["ok"] is True

    @patch("qpopcv.api.psutil.process_iter", side_effect=Exception("unexpected OS error"))
    def test_returns_error_on_unexpected_exception(self, _mock_iter):
        api = make_api()
        result = api.kill_discord()
        assert result["ok"] is False
        assert "error" in result


# ── start_watch discord check ─────────────────────────────────────────────

class TestStartWatchDiscordCheck:

    def _start(self, api, MockWatcher, skip=False):
        MockWatcher.return_value.oversized_refs = []
        return api.start_watch({
            "webhook_url": VALID_WEBHOOK,
            "user_id": VALID_USER_ID,
            "reference_image_paths": [],
            "monitor_index": 0,
            "afk_notify": False,
            "skip_discord_check": skip,
        })

    @patch("qpopcv.api.save_config")
    @patch("qpopcv.api._validate_ref_images", return_value=None)
    @patch("qpopcv.api.QPopWatcher")
    @patch("qpopcv.api._is_discord_running", return_value=True)
    def test_returns_discord_running_when_detected(self, _dc, MockWatcher, _val, _save):
        api = make_api()
        result = self._start(api, MockWatcher, skip=False)
        assert result["ok"] is False
        assert result.get("discord_running") is True

    @patch("qpopcv.api.save_config")
    @patch("qpopcv.api._validate_ref_images", return_value=None)
    @patch("qpopcv.api.QPopWatcher")
    @patch("qpopcv.api._is_discord_running", return_value=True)
    def test_skip_flag_bypasses_discord_check(self, _dc, MockWatcher, _val, _save):
        api = make_api()
        result = self._start(api, MockWatcher, skip=True)
        assert result["ok"] is True

    @patch("qpopcv.api.save_config")
    @patch("qpopcv.api._validate_ref_images", return_value=None)
    @patch("qpopcv.api.QPopWatcher")
    @patch("qpopcv.api._is_discord_running", return_value=False)
    def test_proceeds_when_discord_not_running(self, _dc, MockWatcher, _val, _save):
        api = make_api()
        result = self._start(api, MockWatcher, skip=False)
        assert result["ok"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_api_discord_check.py -v
```

Expected: All tests FAIL. `_is_discord_running` and `kill_discord` don't exist yet. You should see `ImportError: cannot import name '_is_discord_running' from 'qpopcv.api'`.

---

## Task 3: Implement Discord detection in api.py

**Files:**
- Modify: `qpopcv/api.py`

- [ ] **Step 1: Add psutil import**

At the top of `qpopcv/api.py`, the imports currently start with:
```python
from __future__ import annotations

import logging
import threading
import time
import webbrowser
import requests
```

Add `psutil` after `requests`:
```python
from __future__ import annotations

import logging
import threading
import time
import webbrowser
import psutil
import requests
```

- [ ] **Step 2: Add _is_discord_running helper**

Find the module-level validator functions in `api.py` (around lines 30–55, where `_validate_discord` and `_validate_ref_images` are defined). Add `_is_discord_running` after them:

```python
def _is_discord_running() -> bool:
    """Return True if any Discord.exe process is currently running."""
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.name().lower() == "discord.exe":
                return True
        except psutil.NoSuchProcess:
            pass
    return False
```

- [ ] **Step 3: Add kill_discord method to Api class**

Find `stop_watch` in the `Api` class (around line 155). Add `kill_discord` directly after `stop_watch`:

```python
def kill_discord(self) -> dict:
    """Terminate all running Discord.exe processes."""
    try:
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.name().lower() == "discord.exe":
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception as exc:
        logger.error("kill_discord failed: %s", exc)
        return {"ok": False, "error": str(exc)}
    return {"ok": True}
```

- [ ] **Step 4: Add skip_discord_check to start_watch**

In `start_watch` (line 110), the method currently reads the form data as:
```python
def start_watch(self, data: dict) -> dict:
    webhook_url = str(data.get("webhook_url", "")).strip()
    user_id = str(data.get("user_id", "")).strip()
    paths = [str(p) for p in data.get("reference_image_paths", [])]
    monitor_index = int(data.get("monitor_index", 0))
    afk_notify = bool(data.get("afk_notify", False))
```

Add the new field and the check. Change it to:
```python
def start_watch(self, data: dict) -> dict:
    webhook_url = str(data.get("webhook_url", "")).strip()
    user_id = str(data.get("user_id", "")).strip()
    paths = [str(p) for p in data.get("reference_image_paths", [])]
    monitor_index = int(data.get("monitor_index", 0))
    afk_notify = bool(data.get("afk_notify", False))
    skip_discord_check = bool(data.get("skip_discord_check", False))
```

Then find the two validation calls that follow (roughly lines 117–122):
```python
    err = _validate_discord(webhook_url, user_id)
    if err:
        return {"ok": False, "error": err}
    err = _validate_ref_images(paths)
    if err:
        return {"ok": False, "error": err}
```

Insert the Discord check immediately after them:
```python
    err = _validate_discord(webhook_url, user_id)
    if err:
        return {"ok": False, "error": err}
    err = _validate_ref_images(paths)
    if err:
        return {"ok": False, "error": err}

    if not skip_discord_check and _is_discord_running():
        return {"ok": False, "discord_running": True}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_api_discord_check.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Run full test suite to check no regressions**

```bash
pytest -v
```

Expected: All previously passing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add qpopcv/api.py tests/test_api_discord_check.py
git commit -m "feat: add Discord process detection and kill to api.py"
```

---

## Task 4: Register /api/kill_discord route

**Files:**
- Modify: `qpopcv/app_ui.py:139-149`

- [ ] **Step 1: Add route to do_POST**

In `app_ui.py`, find the `do_POST` handler's route dispatch block. It currently ends around line 149 with the `window_control` block:
```python
            elif path == "/api/save_config":
                result = api.save_config_data(body)
            elif path == "/api/window_control":
                action = body.get("action", "")
                if action == "minimize":
                    app._bridge.request_minimize.emit()
                elif action == "close":
                    app._bridge.request_quit.emit()
                elif action == "drag_start":
                    app._bridge.request_drag.emit()
                result = {"ok": True}
```

Add the new route after `/api/save_config` and before `/api/window_control`:
```python
            elif path == "/api/save_config":
                result = api.save_config_data(body)
            elif path == "/api/kill_discord":
                result = api.kill_discord()
            elif path == "/api/window_control":
```

- [ ] **Step 2: Run full test suite**

```bash
pytest -v
```

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add qpopcv/app_ui.py
git commit -m "feat: register /api/kill_discord route"
```

---

## Task 5: Add Discord warning banner to HTML and CSS

**Files:**
- Modify: `qpopcv/static/index.html`
- Modify: `qpopcv/static/style.css`

- [ ] **Step 1: Add banner element to index.html**

In `index.html`, the footer currently looks like (lines 85–99):
```html
    <!-- ── Footer ─────────────────────────────────────────────────── -->
    <footer class="footer">
      <div class="save-row">
        <button class="save-btn" id="btn-save">Save Configuration</button>
      </div>
      <button class="watch-btn" id="watch-btn">
```

Insert the discord-warn div between the `save-row` div and the `watch-btn` button:
```html
    <!-- ── Footer ─────────────────────────────────────────────────── -->
    <footer class="footer">
      <div class="save-row">
        <button class="save-btn" id="btn-save">Save Configuration</button>
      </div>
      <div class="discord-warn hidden" id="discord-warn">
        <span class="discord-warn-msg">⚠ Discord is running. To receive notifications on your phone, quit Discord here or from the system tray.</span>
        <div class="discord-warn-actions">
          <button class="discord-warn-kill" id="discord-kill-btn">Kill Discord</button>
          <button class="discord-warn-continue" id="discord-continue-btn">Continue Anyway</button>
        </div>
      </div>
      <button class="watch-btn" id="watch-btn">
```

- [ ] **Step 2: Add .discord-warn styles to style.css**

Find the end of the toast styles section in `style.css` (around line 840, just before the `/* ── Detected flash overlay ──` comment). Insert the following block before that comment:

```css
/* ── Discord warning banner ──────────────────────────────────── */

.discord-warn {
  margin: 0 0 8px 0;
  padding: 10px 12px;
  border-radius: var(--radius);
  border: 1px solid rgba(217, 119, 6, 0.35);
  background: rgba(255, 237, 213, 0.85);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.discord-warn-msg {
  display: block;
  font-size: 11px;
  line-height: 1.4;
  color: var(--text);
  margin-bottom: 8px;
}

.discord-warn-actions {
  display: flex;
  gap: 6px;
}

.discord-warn-kill {
  flex: 1;
  padding: 5px 8px;
  font-size: 11px;
  border-radius: calc(var(--radius) - 2px);
  border: 1px solid rgba(220, 38, 38, 0.4);
  background: rgba(254, 226, 226, 0.9);
  color: #dc2626;
  cursor: pointer;
  transition: background 0.15s ease;
}

.discord-warn-kill:hover {
  background: rgba(254, 202, 202, 0.95);
}

.discord-warn-continue {
  flex: 1;
  padding: 5px 8px;
  font-size: 11px;
  border-radius: calc(var(--radius) - 2px);
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.8);
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.15s ease;
}

.discord-warn-continue:hover {
  background: rgba(255, 255, 255, 0.95);
}

```

- [ ] **Step 3: Commit**

```bash
git add qpopcv/static/index.html qpopcv/static/style.css
git commit -m "feat: add Discord warning banner to footer (hidden by default)"
```

---

## Task 6: Wire frontend logic in app.js

**Files:**
- Modify: `qpopcv/static/app.js`

- [ ] **Step 1: Add DOM refs for the new banner elements**

In `app.js`, DOM refs are declared near the top of the file (around line 50 where `afkNotifyCheckbox` is defined). Find the block of `const` declarations for DOM elements and add these three lines in the same area:

```javascript
const discordWarn        = $('discord-warn');
const discordKillBtn     = $('discord-kill-btn');
const discordContinueBtn = $('discord-continue-btn');
```

- [ ] **Step 2: Modify doStartWatch to accept skipDiscordCheck flag and handle discord_running**

`doStartWatch` currently reads (lines 263–285):
```javascript
async function doStartWatch() {
  watchBtn.disabled = true;
  try {
    const result = await apiPost('/api/start_watch', collectFormData());
    if (!result.ok) {
      showToast('error', result.error);
      return;
    }
    if (result.warning) {
      showToast('warning', result.warning, 7000);
    }
    state.watching = true;
    setStatus('watching');
    watchBtn.classList.add('is-watching');
    watchBtnIcon.textContent = '■';
    watchBtnText.textContent = 'Stop';
  } catch (e) {
    showToast('error', 'Failed to start watcher.');
    console.error(e);
  } finally {
    watchBtn.disabled = false;
  }
}
```

Replace it entirely with:
```javascript
async function doStartWatch(skipDiscordCheck = false) {
  watchBtn.disabled = true;
  try {
    const data = { ...collectFormData(), skip_discord_check: skipDiscordCheck };
    const result = await apiPost('/api/start_watch', data);
    if (result.discord_running) {
      discordWarn.classList.remove('hidden');
      return;
    }
    if (!result.ok) {
      showToast('error', result.error);
      return;
    }
    discordWarn.classList.add('hidden');
    if (result.warning) {
      showToast('warning', result.warning, 7000);
    }
    state.watching = true;
    setStatus('watching');
    watchBtn.classList.add('is-watching');
    watchBtnIcon.textContent = '■';
    watchBtnText.textContent = 'Stop';
  } catch (e) {
    showToast('error', 'Failed to start watcher.');
    console.error(e);
  } finally {
    watchBtn.disabled = false;
  }
}
```

- [ ] **Step 3: Add Kill Discord and Continue Anyway event listeners**

Find the watchBtn event listener block in `app.js` (around line 255):
```javascript
watchBtn.addEventListener('click', async () => {
  if (state.watching) {
    await doStopWatch();
  } else {
    await doStartWatch();
  }
});
```

Add the two new listeners immediately after that block:
```javascript
discordKillBtn.addEventListener('click', async () => {
  discordKillBtn.disabled = true;
  try {
    const result = await apiPost('/api/kill_discord');
    if (!result.ok) {
      showToast('error', result.error || 'Failed to kill Discord.');
      return;
    }
    discordWarn.classList.add('hidden');
    await doStartWatch(true);
  } catch (e) {
    showToast('error', 'Failed to kill Discord.');
    console.error(e);
  } finally {
    discordKillBtn.disabled = false;
  }
});

discordContinueBtn.addEventListener('click', async () => {
  discordWarn.classList.add('hidden');
  await doStartWatch(true);
});
```

- [ ] **Step 4: Commit**

```bash
git add qpopcv/static/app.js
git commit -m "feat: wire Discord warning banner — kill and continue actions"
```

---

## Task 7: Bump version

**Files:**
- Modify: `qpopcv/config.py`

- [ ] **Step 1: Update APP_VERSION**

In `qpopcv/config.py`, find:
```python
APP_VERSION = "1.0.39"
```

Change it to:
```python
APP_VERSION = "1.0.40"
```

- [ ] **Step 2: Run full test suite one final time**

```bash
pytest -v
```

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add qpopcv/config.py
git commit -m "chore: bump version to 1.0.40"
```

---

## Verification (end-to-end)

1. **Discord running → banner appears:**
   Launch the app (`python main.py`). Make sure Discord is open in the system tray. Click **Watch**. The amber warning banner should appear above the Watch button. The watch should NOT have started (status stays idle).

2. **Kill Discord path:**
   With the banner visible, click **Kill Discord**. Discord should close, the banner should disappear, and watching should begin (status changes to watching, button shows "Stop").

3. **Continue Anyway path:**
   Re-open Discord. Click **Watch** again (stop first if needed). Banner reappears. Click **Continue Anyway**. Banner disappears, watching begins with Discord still running.

4. **Discord not running → no banner:**
   Quit Discord, click **Watch**. No banner. Watch starts immediately.

5. **Regression check:**
   With Discord closed, run through a normal queue-pop detection cycle and an AFK 28-min cycle to confirm existing behaviour is unchanged.
