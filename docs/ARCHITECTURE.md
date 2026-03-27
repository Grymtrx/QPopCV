# QPopCV — Architecture Overview

> **Purpose of this document:** High-level map of how QPopCV works, intended as a starting-point context for Claude (or any developer) picking up this codebase.

---

## What is QPopCV?

A lightweight Windows desktop app that watches the screen for a World of Warcraft Solo Shuffle queue popup and fires a Discord webhook notification (with a user mention) the moment it appears. Users can step away from their PC while queuing and be pinged on phone or desktop Discord — all while staying within Blizzard's TOS.

**Current version:** `1.0.38`
**Target OS:** Windows (uses `pyautogui`, `os.startfile`, batch scripts)

---

## Module Map

| File                          | Role                                                                 |
| ----------------------------- | -------------------------------------------------------------------- |
| `main.py`                     | Entry point — configures logging, creates `QPopApp`, starts Qt loop  |
| `qpopcv/__init__.py`          | Re-exports `QPopApp`                                                 |
| `qpopcv/app_ui.py`            | Qt shell + embedded HTTP server + SSE bridge (`QPopApp`)            |
| `qpopcv/api.py`               | All business logic — watch control, AFK timer, Discord, updates      |
| `qpopcv/watcher.py`           | Screen detection engine (`QPopWatcher`, `WatcherSettings`)           |
| `qpopcv/config.py`            | Config constants, `load_config`, `save_config`                       |
| `qpopcv/discord_client.py`    | Thin wrapper around Discord webhook HTTP (used by Test button)       |
| `qpopcv/validators.py`        | Input validation (webhook, user ID, reference image path)            |
| `qpopcv/updater.py`           | GitHub release checker and installer (`UpdateManager`, `UpdateInfo`) |
| `qpopcv/theme.py`             | **Deprecated** — artifact from CustomTkinter era, not imported       |
| `qpopcv/static/index.html`    | Single-page UI — 4 tabs: Discord, Capture, Images, AFK              |
| `qpopcv/static/style.css`     | Pearl White glassmorphic theme; all colors via CSS custom properties |
| `qpopcv/static/app.js`        | Frontend logic — fetch API calls, SSE handler, tab switching         |

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                              │
│  configure logging → QPopApp() → Qt event loop             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  QPopApp  (app_ui.py)                       │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  QMainWindow (frameless) + QWebEngineView             │  │
│  │  loads http://127.0.0.1:PORT/                         │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  ThreadingHTTPServer (daemon thread, random port)     │  │
│  │  • GET /            → serves index.html               │  │
│  │  • GET /style.css   → serves style.css                │  │
│  │  • GET /app.js      → serves app.js                   │  │
│  │  • GET /events      → SSE stream                      │  │
│  │  • POST /api/*      → delegates to Api class          │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  _Bridge (QObject) — Qt signal bus                    │  │
│  │  • request_browse → QFileDialog on main thread        │  │
│  │  • request_resize → window resize on main thread      │  │
│  │  • request_minimize / request_quit / request_drag     │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     Api  (api.py)                           │
│                                                             │
│  • get_initial_state()    — config + monitor list           │
│  • start_watch(data)      — validates, starts watcher +     │
│                             arms AFK threading.Timer        │
│  • stop_watch()           — stops watcher, cancels timer    │
│  • save_config_data(data) — persists settings               │
│  • test_discord(data)     — test webhook ping               │
│  • check_for_updates()    — background GitHub check         │
│  • install_update()       — download + install              │
│  • _send_afk_notification() — fires after 28 min            │
└────────────┬────────────────────────┬───────────────────────┘
             │                        │
             ▼ (daemon thread)        ▼ (threading.Timer)
┌────────────────────┐    ┌────────────────────────────────┐
│   QPopWatcher      │    │   AFK Timer (28 min)           │
│   (watcher.py)     │    │                                │
│                    │    │  requests.post(webhook,        │
│ pyautogui.         │    │    "<@user_id> Watch time      │
│   screenshot()     │    │    nearing 30 minutes...")     │
│ pyautogui.         │    └────────────────────────────────┘
│   locate()         │
│ → Discord POST     │    ┌────────────────────────────────┐
└────────────────────┘    │   UpdateManager (daemon)       │
                          │   GitHub API → download + bat  │
                          └────────────────────────────────┘
```

---

## JS ↔ Python Communication

**JS → Python:** All UI actions are `fetch('/api/...', { method: 'POST', body: JSON })` calls. The HTTP server dispatches to `Api` methods and returns JSON.

**Python → JS:** Asynchronous events flow via Server-Sent Events. The JS opens `new EventSource('/events')` at startup. Python calls `push_event(type, data)` (thread-safe queue) which serialises to `data: {"type":"..."}` SSE frames.

| SSE Event type     | Trigger                                  | JS handler          |
|--------------------|------------------------------------------|---------------------|
| `detected`         | Queue popup found by watcher             | `onDetected()`      |
| `update_status`    | Update check completed                   | `onUpdateStatus()`  |
| `update_progress`  | Update install progressed / completed    | `onUpdateProgress()`|
| `heartbeat`        | SSE keepalive every 25s                  | (ignored)           |

---

## Threading Model

```
Qt Main Thread (event loop)
│
├─► HTTP Server Thread (daemon)
│     ThreadingHTTPServer.serve_forever()
│     Each request may spawn its own thread (ThreadingHTTPServer)
│     Communicates back to Qt via _Bridge signals (queued, thread-safe)
│
├─► Watcher Thread (daemon)
│     Spawned on start_watch()
│     Runs QPopWatcher._loop() until _stop_event is set
│     Calls push_event("detected") → SSE queue → JS
│
├─► AFK Timer Thread (daemon threading.Timer)
│     Armed on start_watch() if afk_notify=True
│     Fires _send_afk_notification() after 28 minutes
│     Cancelled on stop_watch() or if a new watch session starts
│
├─► Update Check Thread (daemon)
│     Spawned once after startup
│     check_for_update() → GitHub API
│     Calls push_event("update_status") on result
│
└─► Update Install Thread (daemon)
      Spawned only if user confirms install
      Downloads ZIP, extracts, launches update.bat, calls quit_fn()
```

**Thread safety notes:**
- `Api._push_event()` puts items on a `queue.Queue` — thread-safe by design.
- `_Bridge` signals are Qt queued connections — cross-thread signal emissions are safe.
- `QPopWatcher._seen_once` and `_last_qpop_time` are accessed only from the watcher thread — no lock needed.
- `Api._afk_timer` is set/cleared from both the HTTP server thread and the timer thread. CPython GIL makes individual attribute writes atomic; the double-`None` race with `stop_watch` is benign.

---

## Detection Algorithm

```
Every check_interval seconds (default 0.15s):
│
├── 1. pyautogui.screenshot(region=top_center_third)
│         region = computed from selected monitor via monitor_utils
│
├── 2. For each reference image variant (90%, 100%, 110% scale):
│         pyautogui.locate(reference, screenshot, confidence=0.6)
│
├── 3. State machine:
│         popup appeared (not seen → seen):
│           → _handle_detected_popup()
│               → check 15s throttle
│               → POST Discord webhook "<@user_id> Your Queue has popped!"
│               → call on_detect() → push_event("detected") → SSE → JS flash
│         popup gone (seen → not seen):
│           → reset _seen_once = False
│
└── 4. Wait check_interval, repeat
```

---

## Config Data Flow

```
config.json (repo defaults) + config.local.json (user settings, gitignored)
    │
    ▼ load_config() — merges, migrates legacy keys
    │
    ▼
Api.config dict  ←→  JS form fields (via /api/initial_state + collectFormData)
    │
    ├─ /api/save_config  → save_config_data() → save_config() → config.local.json
    └─ /api/start_watch  → start_watch() → save_config() + QPopWatcher + AFK timer
```

**Config keys:**

| Key                      | Type   | Default   | Description                                          |
| ------------------------ | ------ | --------- | ---------------------------------------------------- |
| `webhook_url`            | str    | (see repo)| Discord webhook endpoint                             |
| `user_id`                | str    | `""`      | 17–19-digit Discord snowflake ID                     |
| `check_interval`         | float  | `0.15`    | Seconds between screen captures (~6.7 FPS)           |
| `confidence`             | float  | `0.6`     | Template match confidence threshold (0–1)            |
| `reference_image_paths`  | list   | `[]`      | Paths to user's custom queue popup screenshots (1–5) |
| `monitor_index`          | int    | `0`       | Which monitor to watch (0 = primary)                 |
| `afk_notify`             | bool   | `False`   | Send AFK Discord ping after 28 min of watching       |

---

## AFK Notification Flow

```
User enables AFK checkbox → clicks Watch
    │
    ▼ /api/start_watch  {afk_notify: true, ...}
    │
    ▼ Api.start_watch()
    │   ├── validates discord + ref images
    │   ├── starts QPopWatcher
    │   └── arms threading.Timer(28*60, _send_afk_notification)
    │
    ▼ 28 minutes later...
    │
    ▼ Api._send_afk_notification()
        └── requests.post(webhook, {"content": "<@user_id> Watch time nearing 30 minutes..."})

User clicks Stop at any time → stop_watch() → timer.cancel()
```

---

## Update Mechanism

```
Startup
    └─► check_for_updates() (background thread)
            GET https://api.github.com/repos/Grymtrx/QPopCV/releases/latest
            Compare tag_name vs APP_VERSION
            → push_event("update_status") → SSE → JS shows clickable label

User clicks "Update available: x.x.x"
    └─► /api/install_update → install_update() (background thread)
            Download .zip from GitHub release assets → temp dir
            Extract zip

            If frozen (.exe):
                Write update.bat → os.startfile() → runs after process exits
                bat: waits for exe → xcopy → restart exe → clean temp

            If source:
                _copy_tree() → directly overwrites files in app_dir
                (skips config.json and hidden files)
```

---

## External Dependencies

| Package               | Used For                                         |
| --------------------- | ------------------------------------------------ |
| `PyQt6`               | Qt application framework, event loop             |
| `PyQt6-WebEngine`     | QWebEngineView for rendering the HTML/CSS/JS UI  |
| `pyautogui`           | Screenshot + template matching                   |
| `Pillow`              | Image loading and scaling                        |
| `requests`            | Discord webhooks, GitHub API, update download    |
