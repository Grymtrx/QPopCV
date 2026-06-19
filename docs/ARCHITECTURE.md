# QPopCV — Architecture Overview

> **Purpose of this document:** High-level map of how QPopCV works, intended as a starting-point context for Claude (or any developer) picking up this codebase.

---

## What is QPopCV?

A lightweight Windows desktop app that watches the screen for a World of Warcraft Solo Shuffle queue popup and fires a Discord notification (with a user mention) the moment it appears. The app POSTs to a Cloudflare Worker proxy that holds the real Discord webhook secret and forwards the message — keeping the webhook URL out of the distributed client. Users can step away from their PC while queuing and be pinged on phone or desktop Discord — all while staying within Blizzard's TOS.

**Current version:** `1.2.3`
**Target OS:** Windows (uses `pyautogui`, `os.startfile`, batch scripts)

---

## Module Map

| File                          | Role                                                                 |
| ----------------------------- | -------------------------------------------------------------------- |
| `main.py`                     | Entry point — configures logging, creates `QPopApp`, starts Qt loop  |
| `qpopcv/__init__.py`          | Re-exports `QPopApp`                                                 |
| `qpopcv/app_ui.py`            | Qt shell + embedded HTTP server + SSE bridge (`QPopApp`)            |
| `qpopcv/api.py`               | All business logic — watch control, AFK timer, Discord, metrics, updates |
| `qpopcv/watcher.py`           | Screen detection engine (`QPopWatcher`, `WatcherSettings`)           |
| `qpopcv/config.py`            | Config constants, `load_config`, `save_config`                       |
| `qpopcv/messages.py`          | Timer delay constants + Discord message templates                    |
| `qpopcv/metrics.py`           | Persistent session metrics (`MetricsStore`)                          |
| `qpopcv/discord_client.py`    | Thin wrapper that POSTs `{user_id, type}` to the Cloudflare Worker proxy |
| `qpopcv/validators.py`        | Input validation (user ID, reference image path)                     |
| `qpopcv/updater.py`           | GitHub release checker and installer (`UpdateManager`, `UpdateInfo`) |
| `qpopcv/monitor_utils.py`     | Multi-monitor enumeration + region math                              |
| `qpopcv/font_loader.py`       | Font loading utility                                                 |
| `qpopcv/theme.py`             | **Deprecated** — artifact from CustomTkinter era, not imported       |
| `qpopcv/static/index.html`    | Single-page UI — 5 tabs: Discord, Capture, Images, AFK, Metrics     |
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
│  │  _MainWindow (frameless, always-on-top, dims unfocused)│  │
│  │  + QWebEngineView loads http://127.0.0.1:PORT/        │  │
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
│  │  • request_flash  → taskbar flash on AFK warning      │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     Api  (api.py)                           │
│                                                             │
│  • get_initial_state()    — config + monitor list + metrics │
│  • start_watch(data)      — validates, starts watcher +     │
│                             arms AFK timer, records session │
│  • stop_watch(detected)   — stops watcher, cancels timers,  │
│                             records session to MetricsStore │
│  • kill_discord()         — terminates Discord.exe processes│
│  • save_config_data(data) — persists settings               │
│  • test_discord(data)     — test webhook ping               │
│  • reset_afk()            — cancels escalation, restarts    │
│                             AFK timer, resumes session clock│
│  • check_for_updates()    — background GitHub check         │
│  • install_update()       — download + install              │
│  • _send_afk_warning()    — fires after 28 min              │
│  • _send_afk_logout()     — fires 2 min after warning       │
│  • _end_session(detected) — records to MetricsStore         │
└────────────┬──────────────────────────┬─────────────────────┘
             │                          │
             ▼ (daemon thread)          ▼ (threading.Timer ×2)
┌────────────────────┐    ┌────────────────────────────────────┐
│   QPopWatcher      │    │   AFK Warning Timer (28 min)       │
│   (watcher.py)     │    │                                    │
│                    │    │  POST PROXY_URL {user_id, "afk_warn"}│
│ pyautogui.         │    │  → push_event("afk_warning")       │
│   screenshot()     │    │  → arms Escalation Timer (2 min)   │
│ pyautogui.         │    └────────────────────────────────────┘
│   locate()         │
│ → POST PROXY_URL   │    ┌────────────────────────────────────┐
│ → on_detect()      │    │   AFK Escalation Timer (2 min)     │
└────────────────────┘    │                                    │
                          │  POST PROXY_URL {user_id, "afk_logout"}│
                          │  → push_event("afk_logout")        │
                          └────────────────────────────────────┘

                          ┌────────────────────────────────────┐
                          │   UpdateManager (daemon)           │
                          │   GitHub API → download + bat      │
                          └────────────────────────────────────┘
```

---

## JS ↔ Python Communication

**JS → Python:** All UI actions are `fetch('/api/...', { method: 'POST', body: JSON })` calls. The HTTP server dispatches to `Api` methods and returns JSON.

**Python → JS:** Asynchronous events flow via Server-Sent Events. The JS opens `new EventSource('/events')` at startup. Python calls `push_event(type, data)` (thread-safe queue) which serialises to `data: {"type":"..."}` SSE frames.

| SSE Event type     | Trigger                                        | JS handler             |
|--------------------|------------------------------------------------|------------------------|
| `detected`         | Queue popup found by watcher; watch auto-stops | `onDetected()`         |
| `update_status`    | Update check completed                         | `onUpdateStatus()`     |
| `update_progress`  | Update install progressed / completed          | `onUpdateProgress()`   |
| `afk_warning`      | 28-min AFK warning fired                       | `onAfkWarning()`       |
| `afk_logout`       | 2-min escalation logout message sent           | `onAfkLogout()`        |
| `afk_reset`        | User clicked Reset AFK Timer                   | `onAfkReset()`         |
| `metrics_update`   | Session ended; metrics recomputed              | `onMetricsUpdate()`    |
| `heartbeat`        | SSE keepalive every 25s                        | (ignored)              |

---

## HTTP API Routes

| Method | Path                   | Handler                        | Description                              |
|--------|------------------------|--------------------------------|------------------------------------------|
| POST   | `/api/initial_state`   | `api.get_initial_state()`      | Config + monitors + metrics on load      |
| POST   | `/api/start_watch`     | `api.start_watch(body)`        | Validate, save, start watcher + AFK timer|
| POST   | `/api/stop_watch`      | `api.stop_watch()`             | Stop watcher, cancel timers, end session |
| POST   | `/api/test_discord`    | `api.test_discord(body)`       | Send test webhook ping (throttled 1s)    |
| POST   | `/api/browse_image`    | `app.browse_image_sync()`      | Open native file dialog (main thread)    |
| POST   | `/api/open_discord`    | `api.open_discord()`           | Open Discord server invite in browser    |
| POST   | `/api/check_updates`   | `api.check_for_updates()`      | Kick off background GitHub check         |
| POST   | `/api/install_update`  | `api.install_update()`         | Download + install update                |
| POST   | `/api/resize`          | `app.resize_window(h)`         | Resize Qt window to content height       |
| POST   | `/api/save_config`     | `api.save_config_data(body)`   | Persist settings without starting watcher|
| POST   | `/api/kill_discord`    | `api.kill_discord()`           | Terminate Discord.exe processes          |
| POST   | `/api/reset_afk`       | `api.reset_afk()`              | Cancel escalation, restart AFK timer     |
| POST   | `/api/window_control`  | bridge signals                 | minimize / close / drag_start            |

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
│     Calls on_detect() → Api._on_detection() → stop_watch(detected=True)
│     → push_event("detected") → SSE queue → JS
│
├─► AFK Warning Timer Thread (daemon threading.Timer)
│     Armed on start_watch() if afk_notify=True
│     Fires _send_afk_warning() after 28 minutes (AFK_WARN_DELAY)
│     Cancelled on stop_watch() or when a new watch session starts
│     On fire: sends Discord ping, pushes "afk_warning" SSE,
│              arms Escalation Timer
│
├─► AFK Escalation Timer Thread (daemon threading.Timer)
│     Armed by _send_afk_warning()
│     Fires _send_afk_logout() after 2 minutes (AFK_LOGOUT_DELAY)
│     Cancelled by reset_afk() or stop_watch()
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
- `Api._session_lock` (threading.Lock) guards session start/pause/end fields accessed from both the HTTP server thread and AFK timer threads.
- `Api._afk_timer` / `_afk_escalation_timer` single-attribute writes are atomic under CPython's GIL; see `GAP-08` in KNOWN_ISSUES.md.

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
│               → POST PROXY_URL {user_id, "qpop"}
│               → call on_detect() → Api._on_detection()
│                   → stop_watch(detected=True) + push_event("detected")
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
    │   ├── checks for Discord.exe (warns if running)
    │   ├── starts QPopWatcher
    │   ├── records session start time
    │   └── arms AFK Warning Timer (28 min)
    │
    ▼ 28 minutes later...
    │
    ▼ Api._send_afk_warning()
    │   ├── POST PROXY_URL {user_id, "afk_warn"}
    │   ├── push_event("afk_warning") → JS shows AFK banner + pauses watch timer
    │   │   → _Bridge.request_flash → taskbar icon flashes
    │   └── arms AFK Escalation Timer (2 min)
    │
    ▼ User clicks "Reset AFK Timer" in banner:
    │   Api.reset_afk()
    │   ├── cancels escalation timer
    │   ├── resumes session clock
    │   ├── restarts 28-min AFK timer
    │   └── push_event("afk_reset") → JS hides banner + resumes watch timer
    │
    OR...
    │
    ▼ 2 minutes later (no reset)...
    │
    ▼ Api._send_afk_logout()
        ├── POST PROXY_URL {user_id, "afk_logout"}
        └── push_event("afk_logout") → JS stops watch, resets UI to idle

User clicks Stop at any time → stop_watch() → both timers cancelled
```

---

## Metrics Flow

```
Session starts → Api.start_watch() records _session_start_time, _session_start_mono
    │
    ▼ While watching:
    │   AFK warning pauses effective time (_session_paused_at set)
    │   AFK reset resumes effective time (_session_paused_total accumulates)
    │
    ▼ Session ends (stop_watch() or detection):
    │
    ▼ Api._end_session(detected)
    │   ├── computes duration = elapsed_mono - _session_paused_total
    │   ├── MetricsStore.record_session(start, end, duration, detected)
    │   │     → appends to sessions list → atomic write to metrics.json
    │   └── push_event("metrics_update", {all_time: ..., today: ...})
    │         → JS updates Metrics tab display
    │
    ▼ MetricsStore.compute(day=None)
        Returns: total_time_saved, effective_time_saved, pops_detected,
                 avg_queue_wait, longest_session
        (filtered by day if provided)
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
            Verify SHA-256 checksum (if digest present in release metadata)
            Extract zip

            If frozen (.exe):
                Write update.bat → os.startfile() → runs after process exits
                bat: waits for exe → xcopy → restart exe → clean temp

            If source:
                _copy_tree() → directly overwrites files in app_dir
                (skips config.json and hidden files)
```

---

## Discord Notification Proxy

All Discord pings (queue pop, AFK warning, AFK logout, test) flow through a Cloudflare Worker rather than going directly from the desktop client to Discord. The app POSTs `{user_id, type}` to the `PROXY_URL` constant in `qpopcv/config.py`; the worker looks up `type` (`qpop` / `afk_warn` / `afk_logout` / `test`), formats the message with the user's mention, and forwards to the real Discord webhook. The actual webhook URL is stored as a `wrangler secret` and never ships with the client binary — this prevents the kind of webhook abuse that occurred when the URL leaked via git history. The worker source lives in `worker/` (Wrangler config, `src/index.ts`, README) and is deployed independently of the desktop app.

---

## External Dependencies

| Package               | Used For                                         |
| --------------------- | ------------------------------------------------ |
| `PyQt6`               | Qt application framework, event loop             |
| `PyQt6-WebEngine`     | QWebEngineView for rendering the HTML/CSS/JS UI  |
| `pyautogui`           | Screenshot + template matching                   |
| `Pillow`              | Image loading and scaling                        |
| `requests`            | Cloudflare Worker proxy, GitHub API, update download |
| `psutil`              | Discord process detection (`kill_discord`)       |
