# AFK Notification Improvement & Metrics Tab — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the AFK notification with in-app warning banner, reset timer flow, 2-minute auto-logout escalation, and add a new Metrics tab with persistent session tracking.

**Architecture:** Python-side session tracking and AFK timer escalation in `api.py`, metrics persistence in a new `metrics.py` module, new SSE events for AFK state changes, JS-side watch timer with pause/resume, AFK banner overlay, and Metrics tab with All Time/Today toggle.

**Tech Stack:** Python 3.14, PyQt6, HTML/CSS/JS, pytest, threading.Timer, JSON file persistence

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `qpopcv/metrics.py` | Load/save/compute metrics from `metrics.json` |
| Create | `tests/test_metrics.py` | Tests for metrics module |
| Create | `tests/test_api_afk_reset.py` | Tests for AFK reset + escalation + session tracking |
| Modify | `qpopcv/api.py` | AFK escalation timers, session tracking, reset_afk endpoint, metrics integration |
| Modify | `qpopcv/app_ui.py:117-151` | Add `/api/reset_afk` route, add `request_flash` bridge signal |
| Modify | `qpopcv/config.py:19` | Bump version to `1.2.0` |
| Modify | `qpopcv/static/index.html:34-106` | Add Metrics tab, AFK banner, watch timer element |
| Modify | `qpopcv/static/app.js` | Watch timer logic, AFK banner handling, Metrics tab, new SSE events |
| Modify | `qpopcv/static/style.css` | Watch timer styles, AFK banner styles, Metrics tab styles |
| Modify | `.gitignore` | Add `metrics.json` |

---

### Task 1: Add `metrics.json` to `.gitignore`

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add metrics.json to gitignore**

In `.gitignore`, add after the `config.local.json` line (line 39):

```
metrics.json
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add metrics.json to gitignore"
```

---

### Task 2: Create metrics persistence module

**Files:**
- Create: `qpopcv/metrics.py`
- Create: `tests/test_metrics.py`

- [ ] **Step 1: Write failing tests for metrics module**

Create `tests/test_metrics.py`:

```python
"""Tests for qpopcv/metrics.py — session persistence and metric computation."""
import json
import pytest
from pathlib import Path
from datetime import datetime, date

from qpopcv.metrics import MetricsStore


@pytest.fixture
def store(tmp_path):
    return MetricsStore(tmp_path / "metrics.json")


class TestMetricsStore:

    def test_load_empty_file(self, store):
        """No file yet → empty sessions list."""
        assert store.sessions == []

    def test_record_session(self, store):
        store.record_session(
            start=datetime(2026, 3, 28, 14, 0, 0),
            end=datetime(2026, 3, 28, 14, 12, 38),
            duration_seconds=758,
            detected=True,
        )
        assert len(store.sessions) == 1
        s = store.sessions[0]
        assert s["duration_seconds"] == 758
        assert s["detected"] is True

    def test_persists_to_disk(self, store):
        store.record_session(
            start=datetime(2026, 3, 28, 14, 0, 0),
            end=datetime(2026, 3, 28, 14, 12, 38),
            duration_seconds=758,
            detected=True,
        )
        # Reload from disk
        store2 = MetricsStore(store._path)
        assert len(store2.sessions) == 1

    def test_multiple_sessions(self, store):
        for i in range(3):
            store.record_session(
                start=datetime(2026, 3, 28, 14, i * 20, 0),
                end=datetime(2026, 3, 28, 14, i * 20 + 12, 0),
                duration_seconds=720,
                detected=(i % 2 == 0),
            )
        assert len(store.sessions) == 3


class TestMetricsCompute:

    def _store_with_data(self, tmp_path):
        store = MetricsStore(tmp_path / "metrics.json")
        # Session 1: 12m 38s, detected
        store.record_session(
            start=datetime(2026, 3, 28, 14, 0, 0),
            end=datetime(2026, 3, 28, 14, 12, 38),
            duration_seconds=758,
            detected=True,
        )
        # Session 2: 45m, not detected (manual stop)
        store.record_session(
            start=datetime(2026, 3, 28, 15, 0, 0),
            end=datetime(2026, 3, 28, 15, 45, 0),
            duration_seconds=2700,
            detected=False,
        )
        # Session 3: 20m, detected (different day)
        store.record_session(
            start=datetime(2026, 3, 27, 10, 0, 0),
            end=datetime(2026, 3, 27, 10, 20, 0),
            duration_seconds=1200,
            detected=True,
        )
        return store

    def test_compute_all_time(self, tmp_path):
        store = self._store_with_data(tmp_path)
        m = store.compute()
        assert m["total_time_saved"] == 758 + 2700 + 1200
        assert m["effective_time_saved"] == 758 + 1200
        assert m["pops_detected"] == 2
        assert m["avg_queue_wait"] == (758 + 1200) // 2
        assert m["longest_session"] == 2700

    def test_compute_today(self, tmp_path):
        store = self._store_with_data(tmp_path)
        m = store.compute(day=date(2026, 3, 28))
        assert m["total_time_saved"] == 758 + 2700
        assert m["effective_time_saved"] == 758
        assert m["pops_detected"] == 1
        assert m["avg_queue_wait"] == 758
        assert m["longest_session"] == 2700

    def test_compute_empty(self, tmp_path):
        store = MetricsStore(tmp_path / "metrics.json")
        m = store.compute()
        assert m["total_time_saved"] == 0
        assert m["effective_time_saved"] == 0
        assert m["pops_detected"] == 0
        assert m["avg_queue_wait"] == 0
        assert m["longest_session"] == 0

    def test_compute_no_pops_day(self, tmp_path):
        store = self._store_with_data(tmp_path)
        m = store.compute(day=date(2026, 3, 26))  # no sessions this day
        assert m["pops_detected"] == 0
        assert m["avg_queue_wait"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qpopcv.metrics'`

- [ ] **Step 3: Write metrics module**

Create `qpopcv/metrics.py`:

```python
"""Persistent session metrics for QPopCV."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricsStore:
    """Load, record, and compute session metrics from a JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self.sessions: List[Dict] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self.sessions = []
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self.sessions = data.get("sessions", [])
        except Exception as exc:
            logger.warning("Failed to load metrics: %s", exc)
            self.sessions = []

    def _save(self) -> None:
        self._path.write_text(
            json.dumps({"sessions": self.sessions}, indent=2),
            encoding="utf-8",
        )

    def record_session(
        self,
        start: datetime,
        end: datetime,
        duration_seconds: int,
        detected: bool,
    ) -> Dict:
        session = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "duration_seconds": duration_seconds,
            "detected": detected,
        }
        self.sessions.append(session)
        self._save()
        return session

    def compute(self, day: Optional[date] = None) -> Dict:
        filtered = self.sessions
        if day is not None:
            filtered = [
                s for s in self.sessions
                if datetime.fromisoformat(s["start"]).date() == day
            ]

        total = sum(s["duration_seconds"] for s in filtered)
        detected_sessions = [s for s in filtered if s["detected"]]
        effective = sum(s["duration_seconds"] for s in detected_sessions)
        pops = len(detected_sessions)
        avg = effective // pops if pops > 0 else 0
        longest = max((s["duration_seconds"] for s in filtered), default=0)

        return {
            "total_time_saved": total,
            "effective_time_saved": effective,
            "pops_detected": pops,
            "avg_queue_wait": avg,
            "longest_session": longest,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_metrics.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add qpopcv/metrics.py tests/test_metrics.py
git commit -m "feat: add metrics persistence module with session recording and computation"
```

---

### Task 3: Add AFK escalation timers, session tracking, and reset endpoint to API

**Files:**
- Modify: `qpopcv/api.py`
- Create: `tests/test_api_afk_reset.py`

- [ ] **Step 1: Write failing tests for AFK reset and escalation**

Create `tests/test_api_afk_reset.py`:

```python
"""Tests for AFK reset, escalation, and session tracking in qpopcv/api.py."""
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime

from qpopcv.api import Api

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


def make_api(config=None, push_event=None):
    if config is None:
        config = make_config()
    if push_event is None:
        push_event = MagicMock()
    return Api(config, push_event=push_event)


class TestAfkEscalation:

    @patch("qpopcv.api.requests.post")
    def test_send_afk_warning_pushes_sse_event(self, mock_post):
        push = MagicMock()
        api = make_api(push_event=push)
        api._send_afk_warning()
        push.assert_any_call("afk_warning", None)

    @patch("qpopcv.api.requests.post")
    def test_send_afk_warning_sends_discord_message(self, mock_post):
        api = make_api()
        api._send_afk_warning()
        mock_post.assert_called_once()
        content = mock_post.call_args[1]["json"]["content"]
        assert "Move character to prevent AFK logout" in content
        assert f"<@{VALID_USER_ID}>" in content

    @patch("qpopcv.api.requests.post")
    def test_send_afk_warning_creates_escalation_timer(self, mock_post):
        api = make_api()
        api._send_afk_warning()
        assert api._afk_escalation_timer is not None

    @patch("qpopcv.api.requests.post")
    def test_send_afk_logout_sends_second_discord(self, mock_post):
        api = make_api()
        api._send_afk_logout()
        mock_post.assert_called_once()
        content = mock_post.call_args[1]["json"]["content"]
        assert "auto-logged out" in content

    @patch("qpopcv.api.requests.post")
    def test_send_afk_logout_pushes_sse_event(self, mock_post):
        push = MagicMock()
        api = make_api(push_event=push)
        api._send_afk_logout()
        push.assert_any_call("afk_logout", None)


class TestAfkReset:

    @patch("qpopcv.api.threading.Timer")
    def test_reset_afk_restarts_timer(self, MockTimer):
        push = MagicMock()
        api = make_api(make_config(afk_notify=True), push_event=push)
        # Simulate AFK state
        api._afk_warned = True
        mock_esc = MagicMock()
        api._afk_escalation_timer = mock_esc
        result = api.reset_afk()
        assert result["ok"] is True
        mock_esc.cancel.assert_called_once()
        MockTimer.assert_called_once()
        push.assert_any_call("afk_reset", None)

    def test_reset_afk_when_not_warned_returns_error(self):
        api = make_api()
        api._afk_warned = False
        result = api.reset_afk()
        assert result["ok"] is False


class TestSessionTracking:

    @patch("qpopcv.api._validate_ref_images", return_value=None)
    @patch("qpopcv.api.QPopWatcher")
    @patch("qpopcv.api._is_discord_running", return_value=False)
    def test_start_watch_records_session_start(self, _dc, MockWatcher, _val):
        api = make_api()
        MockWatcher.return_value.oversized_refs = []
        api.start_watch({
            "webhook_url": VALID_WEBHOOK,
            "user_id": VALID_USER_ID,
            "reference_image_paths": [],
            "monitor_index": 0,
            "afk_notify": False,
        })
        assert api._session_start_time is not None
        assert api._session_paused_total == 0.0

    @patch("qpopcv.api._validate_ref_images", return_value=None)
    @patch("qpopcv.api.QPopWatcher")
    @patch("qpopcv.api._is_discord_running", return_value=False)
    def test_stop_watch_records_session(self, _dc, MockWatcher, _val):
        api = make_api()
        MockWatcher.return_value.oversized_refs = []
        api.start_watch({
            "webhook_url": VALID_WEBHOOK,
            "user_id": VALID_USER_ID,
            "reference_image_paths": [],
            "monitor_index": 0,
            "afk_notify": False,
        })
        result = api.stop_watch()
        assert result["ok"] is True
        assert "session" in result
        assert result["session"]["detected"] is False
        assert result["session"]["duration_seconds"] >= 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api_afk_reset.py -v`
Expected: FAIL — `AttributeError: 'Api' object has no attribute '_send_afk_warning'`

- [ ] **Step 3: Implement AFK escalation, reset, and session tracking in api.py**

Modify `qpopcv/api.py`. Changes needed:

**Add import** at top (after existing imports, line 15):

```python
from datetime import datetime, date
from .metrics import MetricsStore
```

**Add to `__init__`** (after line 92):

```python
        self._afk_escalation_timer: Optional[threading.Timer] = None
        self._afk_warned: bool = False
        self._session_start_time: Optional[datetime] = None
        self._session_paused_at: Optional[float] = None
        self._session_paused_total: float = 0.0
        self._metrics = MetricsStore(APP_DIR / "metrics.json")
```

**Replace `start_watch` session tracking** — after line 149 (`self._watcher.start()`), before the AFK timer block, add:

```python
        self._session_start_time = datetime.now()
        self._session_paused_at = None
        self._session_paused_total = 0.0
        self._afk_warned = False
```

**Replace the AFK timer block** (lines 151–158) — the timer now calls `_send_afk_warning` instead of `_send_afk_notification`:

```python
        if self._afk_timer:
            self._afk_timer.cancel()
            self._afk_timer = None
        if self._afk_escalation_timer:
            self._afk_escalation_timer.cancel()
            self._afk_escalation_timer = None

        if afk_notify:
            self._afk_timer = threading.Timer(28 * 60, self._send_afk_warning)
            self._afk_timer.daemon = True
            self._afk_timer.start()
```

**Replace `stop_watch`** (lines 171–178):

```python
    def stop_watch(self, detected: bool = False) -> dict:
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
        if self._afk_timer:
            self._afk_timer.cancel()
            self._afk_timer = None
        if self._afk_escalation_timer:
            self._afk_escalation_timer.cancel()
            self._afk_escalation_timer = None
        self._afk_warned = False

        session = self._end_session(detected)
        return {"ok": True, "session": session}
```

**Add new methods** after `_on_detection` (line 269):

```python
    def _on_detection(self) -> None:
        """Called from QPopWatcher daemon thread on queue-pop detection."""
        self.stop_watch(detected=True)
        self._push("detected", None)

    def _send_afk_warning(self) -> None:
        """Called by threading.Timer after 28 minutes of watching."""
        self._afk_warned = True
        self._session_paused_at = time.monotonic()

        webhook_url = str(self.config.get("webhook_url", "")).strip()
        user_id = str(self.config.get("user_id", "")).strip()
        if webhook_url and user_id:
            content = (
                f"<@{user_id}> Move character to prevent AFK logout. "
                "Watch time nearing 30 minutes."
            )
            try:
                requests.post(webhook_url, json={"content": content}, timeout=5)
            except Exception as exc:
                logger.error("AFK warning notification failed: %s", exc)

        self._push("afk_warning", None)

        self._afk_escalation_timer = threading.Timer(2 * 60, self._send_afk_logout)
        self._afk_escalation_timer.daemon = True
        self._afk_escalation_timer.start()

    def _send_afk_logout(self) -> None:
        """Called 2 minutes after AFK warning if user hasn't reset."""
        webhook_url = str(self.config.get("webhook_url", "")).strip()
        user_id = str(self.config.get("user_id", "")).strip()
        if webhook_url and user_id:
            content = (
                f"<@{user_id}> Your character has most likely auto-logged out. "
                "Return to PC."
            )
            try:
                requests.post(webhook_url, json={"content": content}, timeout=5)
            except Exception as exc:
                logger.error("AFK logout notification failed: %s", exc)

        self._afk_escalation_timer = None
        self._push("afk_logout", None)

    def reset_afk(self) -> dict:
        """Reset the AFK timer — called when user clicks Reset AFK Timer button."""
        if not self._afk_warned:
            return {"ok": False, "error": "No AFK warning active."}

        if self._afk_escalation_timer:
            self._afk_escalation_timer.cancel()
            self._afk_escalation_timer = None

        # Resume session timer
        if self._session_paused_at is not None:
            self._session_paused_total += time.monotonic() - self._session_paused_at
            self._session_paused_at = None

        self._afk_warned = False

        # Restart 28-min AFK timer
        if self._afk_timer:
            self._afk_timer.cancel()
        self._afk_timer = threading.Timer(28 * 60, self._send_afk_warning)
        self._afk_timer.daemon = True
        self._afk_timer.start()

        self._push("afk_reset", None)
        return {"ok": True}

    def _end_session(self, detected: bool) -> Optional[dict]:
        """Record session to metrics store. Returns session dict or None."""
        if self._session_start_time is None:
            return None

        now = datetime.now()
        elapsed_wall = (now - self._session_start_time).total_seconds()

        # If currently paused, add the current pause duration
        if self._session_paused_at is not None:
            self._session_paused_total += time.monotonic() - self._session_paused_at
            self._session_paused_at = None

        duration = max(0, int(elapsed_wall - self._session_paused_total))

        session = self._metrics.record_session(
            start=self._session_start_time,
            end=now,
            duration_seconds=duration,
            detected=detected,
        )

        self._session_start_time = None
        self._session_paused_total = 0.0

        # Push updated metrics to JS
        self._push("metrics_update", {
            "all_time": self._metrics.compute(),
            "today": self._metrics.compute(day=date.today()),
        })

        return session
```

**Update `get_initial_state`** — add metrics to the return dict (after line 117, `"monitors": labels`):

```python
            "metrics": {
                "all_time": self._metrics.compute(),
                "today": self._metrics.compute(day=date.today()),
            },
```

**Update `_cleanup`** — add escalation timer cleanup (after line 293):

```python
        if self._afk_escalation_timer:
            self._afk_escalation_timer.cancel()
            self._afk_escalation_timer = None
```

**Remove the old `_send_afk_notification` method** (lines 271–285) — it's replaced by `_send_afk_warning`.

- [ ] **Step 4: Update existing AFK tests**

In `tests/test_api_afk.py`, update:

- Line 85: Change `api._send_afk_notification` → `api._send_afk_warning` in the Timer assertion
- Lines 34, 36: The `_send_afk_notification` tests in `TestSendAfkNotification` class should be renamed/updated to test `_send_afk_warning` instead. Update the test method names and the method calls from `api._send_afk_notification()` to `api._send_afk_warning()`. Update the assertion from `"30 minutes" in content` to `"Move character to prevent AFK logout" in content`.

- [ ] **Step 5: Run all tests**

Run: `pytest tests/test_api_afk.py tests/test_api_afk_reset.py tests/test_metrics.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add qpopcv/api.py tests/test_api_afk.py tests/test_api_afk_reset.py
git commit -m "feat: add AFK escalation timers, reset endpoint, and session tracking"
```

---

### Task 4: Add `/api/reset_afk` route and taskbar flash bridge

**Files:**
- Modify: `qpopcv/app_ui.py`

- [ ] **Step 1: Add the reset_afk route**

In `qpopcv/app_ui.py`, in the `do_POST` method, add after the `kill_discord` handler (line 142):

```python
            elif path == "/api/reset_afk":
                result = api.reset_afk()
```

- [ ] **Step 2: Add taskbar flash bridge signal and handler**

In `_Bridge` class (line 197), add a new signal:

```python
    request_flash    = pyqtSignal()
```

In `QPopApp.__init__` (after `self._api` creation, around line 226), override `_push_event` to also trigger flash on `afk_warning`:

This is handled by wiring the signal in `run()`. Add after the existing bridge connections (after line 333):

```python
        self._bridge.request_flash.connect(
            self._on_flash_requested, Qt.ConnectionType.QueuedConnection
        )
```

Add the flash handler method to `QPopApp` (after `_on_drag_requested`):

```python
    def _on_flash_requested(self) -> None:
        """Runs on Qt main thread. Flashes the taskbar icon."""
        if self._window:
            app = QApplication.instance()
            if app:
                app.alert(self._window, 0)  # 0 = flash until focused
```

Modify `_push_event` to trigger flash for `afk_warning` events:

```python
    def _push_event(self, event_type: str, data: dict | None = None) -> None:
        """Thread-safe SSE push."""
        payload: dict = {"type": event_type}
        if data:
            payload.update(data)
        self._event_queue.put(payload)
        if event_type == "afk_warning":
            self._bridge.request_flash.emit()
```

- [ ] **Step 3: Run full test suite**

Run: `pytest -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add qpopcv/app_ui.py
git commit -m "feat: add /api/reset_afk route and taskbar flash bridge"
```

---

### Task 5: Add watch timer and AFK banner to HTML

**Files:**
- Modify: `qpopcv/static/index.html`

- [ ] **Step 1: Add Metrics tab button**

In `index.html`, add a 5th tab button inside the `<nav class="tab-bar">` (after line 39, before the closing `</nav>`):

```html
      <button class="tab-btn" data-tab="metrics">Metrics</button>
```

- [ ] **Step 2: Add Metrics tab panel**

After the AFK tab panel closing `</div>` (line 83), add:

```html
    <!-- ── Metrics tab ────────────────────────────────────────────── -->
    <div class="tab-panel" id="tab-metrics">
      <div class="metrics-toggle" id="metrics-toggle">
        <button class="metrics-toggle-btn active" data-period="all">All Time</button>
        <button class="metrics-toggle-btn" data-period="today">Today</button>
      </div>
      <div class="metrics-hero" id="metric-total-time">
        <div class="metrics-hero-label">Total Time Saved</div>
        <div class="metrics-hero-value" id="metric-total-time-val">0m</div>
      </div>
      <div class="metrics-effective" id="metric-effective-time">
        <div class="metrics-effective-label">Effective Time Saved <span class="metrics-effective-tag">(Queue Popped)</span></div>
        <div class="metrics-effective-value" id="metric-effective-time-val">0m</div>
      </div>
      <div class="metrics-row">
        <div class="metrics-stat">
          <div class="metrics-stat-value" id="metric-pops-val">0</div>
          <div class="metrics-stat-label">Pops<br>Detected</div>
        </div>
        <div class="metrics-stat">
          <div class="metrics-stat-value" id="metric-avg-wait-val">0m</div>
          <div class="metrics-stat-label">Avg Queue<br>Wait</div>
        </div>
        <div class="metrics-stat">
          <div class="metrics-stat-value" id="metric-longest-val">0m</div>
          <div class="metrics-stat-label">Longest<br>Session</div>
        </div>
      </div>
    </div>
```

- [ ] **Step 3: Add AFK banner**

After the Metrics tab panel (before the footer), add:

```html
    <!-- ── AFK warning banner ─────────────────────────────────────── -->
    <div class="afk-banner hidden" id="afk-banner">
      <div class="afk-banner-icon">⚠</div>
      <div class="afk-banner-body">
        <div class="afk-banner-title">Move character to prevent AFK logout</div>
        <div class="afk-banner-hint">Then click the button below to reset the 28-minute AFK timer and continue watching.</div>
        <button class="afk-banner-btn" id="afk-reset-btn">Reset AFK Timer</button>
      </div>
    </div>
```

- [ ] **Step 4: Add watch timer element in footer**

In the footer, add the watch timer element before the watch button (before line 97):

```html
      <div class="watch-timer hidden" id="watch-timer">
        <span class="watch-timer-value" id="watch-timer-value">00:00:00</span>
        <span class="watch-timer-paused hidden" id="watch-timer-paused">PAUSED</span>
      </div>
```

- [ ] **Step 5: Commit**

```bash
git add qpopcv/static/index.html
git commit -m "feat: add Metrics tab, AFK banner, and watch timer to HTML"
```

---

### Task 6: Add CSS styles for watch timer, AFK banner, and Metrics tab

**Files:**
- Modify: `qpopcv/static/style.css`

- [ ] **Step 1: Add watch timer styles**

Append after the `.check-hint` block (end of file):

```css
/* ── Watch timer ────────────────────────────────────────────── */

.watch-timer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.watch-timer-value {
  font-family: 'Inter', monospace;
  font-size: 18px;
  font-weight: 700;
  color: var(--green);
  letter-spacing: 1px;
}

.watch-timer.is-paused .watch-timer-value {
  color: var(--orange);
  animation: timer-blink 1s ease-in-out infinite;
}

.watch-timer-paused {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

@keyframes timer-blink {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.3; }
}

/* ── AFK warning banner ─────────────────────────────────────── */

.afk-banner {
  margin: 0 14px 0;
  padding: 14px;
  border-radius: var(--radius);
  border: 1px solid rgba(217, 119, 6, 0.35);
  border-left: 4px solid var(--orange);
  background: linear-gradient(135deg, rgba(254, 243, 199, 0.9), rgba(253, 230, 138, 0.9));
  backdrop-filter: blur(8px);
  display: flex;
  gap: 10px;
  align-items: flex-start;
  animation: afk-pulse 2s ease-in-out infinite;
}

.afk-banner.hidden {
  display: none;
}

.afk-banner-icon {
  font-size: 18px;
  line-height: 1;
  flex-shrink: 0;
}

.afk-banner-body {
  flex: 1;
}

.afk-banner-title {
  font-size: 13px;
  font-weight: 700;
  color: #92400e;
  margin-bottom: 4px;
}

.afk-banner-hint {
  font-size: 11px;
  color: #78350f;
  line-height: 1.4;
  margin-bottom: 10px;
}

.afk-banner-btn {
  width: 100%;
  padding: 7px 16px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--orange);
  color: #fff;
  font-family: 'Inter', sans-serif;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity var(--transition);
}

.afk-banner-btn:hover {
  opacity: 0.85;
}

@keyframes afk-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(217, 119, 6, 0); }
  50%      { box-shadow: 0 0 12px 2px rgba(217, 119, 6, 0.2); }
}

/* ── Metrics tab ────────────────────────────────────────────── */

.metrics-toggle {
  display: flex;
  gap: 0;
  background: rgba(0, 0, 0, 0.06);
  border-radius: var(--radius);
  padding: 3px;
  margin-bottom: 12px;
}

.metrics-toggle-btn {
  flex: 1;
  padding: 5px 0;
  border: none;
  border-radius: calc(var(--radius) - 2px);
  background: transparent;
  font-family: 'Inter', sans-serif;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  transition: background var(--transition), color var(--transition), box-shadow var(--transition);
}

.metrics-toggle-btn.active {
  background: #fff;
  color: var(--text);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.metrics-hero {
  background: linear-gradient(135deg, #ffffff, #f8fafc);
  border-radius: var(--radius);
  padding: 14px;
  border: 1px solid var(--border);
  text-align: center;
  margin-bottom: 8px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.metrics-hero-label {
  font-size: 9px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
}

.metrics-hero-value {
  font-size: 26px;
  font-weight: 800;
  color: var(--text);
  margin-top: 4px;
  letter-spacing: -0.5px;
}

.metrics-effective {
  background: linear-gradient(135deg, rgba(236, 253, 245, 0.9), rgba(209, 250, 229, 0.9));
  border-radius: var(--radius);
  padding: 12px;
  border: 1px solid rgba(16, 185, 129, 0.15);
  text-align: center;
  margin-bottom: 10px;
}

.metrics-effective-label {
  font-size: 9px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
}

.metrics-effective-tag {
  color: var(--green);
  font-weight: 700;
}

.metrics-effective-value {
  font-size: 22px;
  font-weight: 800;
  color: #059669;
  margin-top: 4px;
  letter-spacing: -0.5px;
}

.metrics-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 6px;
}

.metrics-stat {
  background: rgba(255, 255, 255, 0.8);
  border-radius: var(--radius);
  padding: 10px 6px;
  border: 1px solid var(--border);
  text-align: center;
}

.metrics-stat-value {
  font-size: 20px;
  font-weight: 800;
  color: var(--text);
  letter-spacing: -0.5px;
}

.metrics-stat:first-child .metrics-stat-value {
  color: var(--blue);
}

.metrics-stat-label {
  font-size: 8px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
  margin-top: 4px;
  line-height: 1.3;
}
```

- [ ] **Step 2: Commit**

```bash
git add qpopcv/static/style.css
git commit -m "feat: add CSS for watch timer, AFK banner, and Metrics tab"
```

---

### Task 7: Add JavaScript logic for watch timer, AFK banner, Metrics tab, and SSE events

**Files:**
- Modify: `qpopcv/static/app.js`

- [ ] **Step 1: Add state variables and DOM refs**

In the `state` object (after line 31), add:

```javascript
  metricsData: { all_time: null, today: null },
  metricsPeriod: 'all',
  watchTimerInterval: null,
  watchTimerSeconds: 0,
  watchTimerPaused: false,
```

After the existing DOM refs (after line 53), add:

```javascript
const watchTimer        = $('watch-timer');
const watchTimerValue   = $('watch-timer-value');
const watchTimerPaused  = $('watch-timer-paused');
const afkBanner         = $('afk-banner');
const afkResetBtn       = $('afk-reset-btn');
```

- [ ] **Step 2: Add SSE event handlers**

In `handlePushEvent` (line 100), add new cases inside the switch before the `heartbeat` case:

```javascript
    case 'afk_warning':
      onAfkWarning();
      break;
    case 'afk_logout':
      onAfkLogout();
      break;
    case 'afk_reset':
      onAfkReset();
      break;
    case 'metrics_update':
      onMetricsUpdate(event);
      break;
```

- [ ] **Step 3: Add watch timer functions**

After the existing `onDetected` function (after line 210), add:

```javascript
// ── Watch timer ────────────────────────────────────────────────────────────────

function formatHMS(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  return String(h).padStart(2, '0') + ':' +
         String(m).padStart(2, '0') + ':' +
         String(s).padStart(2, '0');
}

function startWatchTimer() {
  state.watchTimerSeconds = 0;
  state.watchTimerPaused = false;
  watchTimerValue.textContent = '00:00:00';
  watchTimer.classList.remove('hidden', 'is-paused');
  watchTimerPaused.classList.add('hidden');

  state.watchTimerInterval = setInterval(() => {
    if (!state.watchTimerPaused) {
      state.watchTimerSeconds++;
      watchTimerValue.textContent = formatHMS(state.watchTimerSeconds);
    }
  }, 1000);
  measureAndResize();
}

function stopWatchTimer() {
  if (state.watchTimerInterval) {
    clearInterval(state.watchTimerInterval);
    state.watchTimerInterval = null;
  }
  watchTimer.classList.add('hidden');
  watchTimer.classList.remove('is-paused');
  watchTimerPaused.classList.add('hidden');
  state.watchTimerPaused = false;
  measureAndResize();
}

function pauseWatchTimer() {
  state.watchTimerPaused = true;
  watchTimer.classList.add('is-paused');
  watchTimerPaused.classList.remove('hidden');
}

function resumeWatchTimer() {
  state.watchTimerPaused = false;
  watchTimer.classList.remove('is-paused');
  watchTimerPaused.classList.add('hidden');
}
```

- [ ] **Step 4: Add AFK banner functions**

After the watch timer functions, add:

```javascript
// ── AFK banner ─────────────────────────────────────────────────────────────────

function onAfkWarning() {
  afkBanner.classList.remove('hidden');
  pauseWatchTimer();
  statusPill.dataset.state = 'afk';
  statusText.textContent = 'AFK Warning';
  measureAndResize();
}

function onAfkLogout() {
  // Banner stays visible, flashing continues
  showToast('warning', 'Your character has most likely auto-logged out.', 8000);
}

function onAfkReset() {
  afkBanner.classList.add('hidden');
  resumeWatchTimer();
  setStatus('watching');
  measureAndResize();
}

afkResetBtn.addEventListener('click', async () => {
  afkResetBtn.disabled = true;
  try {
    const result = await apiPost('/api/reset_afk');
    if (!result.ok) {
      showToast('error', result.error || 'Reset failed.');
    }
  } catch (e) {
    showToast('error', 'Reset request failed.');
  } finally {
    afkResetBtn.disabled = false;
  }
});
```

- [ ] **Step 5: Add Metrics tab functions**

After the AFK banner functions, add:

```javascript
// ── Metrics tab ────────────────────────────────────────────────────────────────

function formatDuration(totalSeconds) {
  if (totalSeconds <= 0) return '0m';
  const d = Math.floor(totalSeconds / 86400);
  const h = Math.floor((totalSeconds % 86400) / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function renderMetrics() {
  const data = state.metricsPeriod === 'all'
    ? state.metricsData.all_time
    : state.metricsData.today;
  if (!data) return;

  $('metric-total-time-val').textContent = formatDuration(data.total_time_saved);
  $('metric-effective-time-val').textContent = formatDuration(data.effective_time_saved);
  $('metric-pops-val').textContent = String(data.pops_detected);
  $('metric-avg-wait-val').textContent = formatDuration(data.avg_queue_wait);
  $('metric-longest-val').textContent = formatDuration(data.longest_session);
}

function onMetricsUpdate(event) {
  state.metricsData.all_time = event.all_time || state.metricsData.all_time;
  state.metricsData.today = event.today || state.metricsData.today;
  renderMetrics();
}

document.querySelectorAll('.metrics-toggle-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.metrics-toggle-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.metricsPeriod = btn.dataset.period;
    renderMetrics();
  });
});
```

- [ ] **Step 6: Wire timer into start/stop watch**

In `doStartWatch` (around line 312), after `state.watching = true;`, add:

```javascript
    startWatchTimer();
```

In `doStopWatch` (around line 329), after `state.watching = false;`, add:

```javascript
    stopWatchTimer();
    afkBanner.classList.add('hidden');
```

- [ ] **Step 7: Wire metrics into initial state**

In `applyInitialState` (around line 134), after the existing code, add:

```javascript
  if (data.metrics) {
    state.metricsData = data.metrics;
    renderMetrics();
  }
```

- [ ] **Step 8: Update onDetected to stop timer**

In `onDetected` (line 198), add at the beginning:

```javascript
  state.watching = false;
  stopWatchTimer();
  afkBanner.classList.add('hidden');
  watchBtn.classList.remove('is-watching');
  watchBtnIcon.textContent = '▶';
  watchBtnText.textContent = 'Watch';
```

- [ ] **Step 9: Add status pill style for AFK state**

In `setStatus` function (line 191), update the text map:

```javascript
  statusText.textContent = { idle: 'Stopped', watching: 'Watching', detected: 'Detected!', afk: 'AFK Warning' }[stateVal] || stateVal;
```

- [ ] **Step 10: Commit**

```bash
git add qpopcv/static/app.js
git commit -m "feat: add watch timer, AFK banner, and Metrics tab JavaScript logic"
```

---

### Task 8: Add AFK status pill CSS style

**Files:**
- Modify: `qpopcv/static/style.css`

- [ ] **Step 1: Find and update status pill styles**

Find the existing status pill styles in `style.css` (look for `[data-state="watching"]` and similar). Add after the last `data-state` rule:

```css
.status-pill[data-state="afk"] {
  background: rgba(217, 119, 6, 0.12);
  border-color: rgba(217, 119, 6, 0.30);
}

.status-pill[data-state="afk"] .status-orb {
  background: var(--orange);
  box-shadow: 0 0 6px var(--orange-glow);
  animation: orb-pulse 1s ease-in-out infinite;
}

.status-pill[data-state="afk"] .status-text {
  color: var(--orange);
}
```

- [ ] **Step 2: Commit**

```bash
git add qpopcv/static/style.css
git commit -m "feat: add AFK warning status pill style"
```

---

### Task 9: Bump version and update detection callback

**Files:**
- Modify: `qpopcv/config.py`

- [ ] **Step 1: Bump version**

In `qpopcv/config.py`, change line 19:

```python
APP_VERSION = "1.2.0"
```

- [ ] **Step 2: Run full test suite**

Run: `pytest -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add qpopcv/config.py
git commit -m "chore: bump version to 1.2.0"
```

---

### Task 10: Integration test and manual verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: All PASS

- [ ] **Step 2: Manual smoke test checklist**

Launch the app and verify:

1. Watch timer appears above Watch button when watching starts, hidden when stopped
2. Watch timer counts up in `HH:MM:SS` format (green)
3. AFK checkbox enabled → after 28 min (or temporarily reduce to 5s for testing):
   - Discord message sent with "Move character to prevent AFK logout"
   - Taskbar flashes
   - AFK banner appears in-app
   - Watch timer turns orange, blinks, shows "PAUSED"
   - Status pill shows "AFK Warning" (amber)
4. Click Reset AFK Timer:
   - Banner dismisses
   - Timer resumes (green)
   - Status returns to "Watching"
5. If reset not clicked within 2 min → second Discord message about auto-logout
6. Stop Watch → session recorded to metrics
7. Metrics tab shows correct All Time / Today stats
8. Toggle between All Time and Today works
9. Window resizes correctly with new elements

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: integration test fixes for AFK and metrics features"
```
