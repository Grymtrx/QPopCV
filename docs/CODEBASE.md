# QPopCV — Codebase Reference

> **Purpose of this document:** Per-file breakdown of every module — classes, functions, data structures, and notable implementation details. Use this as a code map when making targeted changes.

---

## Directory Tree

```
QPopCV/
├── main.py                              Entry point
├── pyproject.toml                       Build config + pytest settings
├── docs/
│   ├── ARCHITECTURE.md                  System overview + diagrams
│   ├── CODEBASE.md                      (this file)
│   ├── KNOWN_ISSUES.md                  Bugs, security issues, tech debt
│   └── superpowers/
│       ├── specs/                       Feature design specs
│       └── plans/                       Implementation plans
├── qpopcv/                              Main package
│   ├── __init__.py                      Re-exports QPopApp
│   ├── app_ui.py                        Qt shell + HTTP server + SSE bridge
│   ├── api.py                           All business logic (framework-agnostic)
│   ├── config.py                        Config management
│   ├── config.json                      Shared/repo config (webhook default)
│   ├── config.local.json                User's personal config (gitignored, auto-created)
│   ├── messages.py                      Timer delay constants + Discord message templates
│   ├── metrics.py                       Persistent session metrics (MetricsStore)
│   ├── discord_client.py                Discord HTTP wrapper
│   ├── watcher.py                       Detection engine
│   ├── validators.py                    Input validation
│   ├── updater.py                       Auto-updater
│   ├── monitor_utils.py                 Multi-monitor enumeration + region math
│   ├── font_loader.py                   Font loading utility
│   ├── theme.py                         Deprecated — CustomTkinter era artifact
│   └── static/
│       ├── index.html                   Single-page UI (5 tabs)
│       ├── style.css                    Pearl White glassmorphic theme
│       └── app.js                       Frontend logic
├── tests/
│   ├── conftest.py                      Pytest fixtures (Python 3.14 compat patches)
│   ├── test_api_afk.py                  AFK timer + notification tests
│   ├── test_api_afk_reset.py            AFK reset + escalation timer tests
│   ├── test_api_discord_check.py        Discord process detection tests
│   ├── test_config.py                   Config load/save tests
│   ├── test_metrics.py                  MetricsStore tests
│   ├── test_updater.py                  Updater logic tests
│   ├── test_validators.py               Input validation tests
│   ├── test_watcher.py                  Watcher engine tests
│   ├── test_capture_region.py           Manual region capture utility
│   └── QpopCV_prototype.py              Original single-file prototype (not automated)
└── tools/
    ├── show_watch_region.py             Visualises the watch region on screen
    └── privacy_mask.py                  Transparent overlay for safe screenshotting
```

---

## `main.py`

**Lines:** ~28

Entry point. Configures logging and starts the app.

```python
def main() -> None
```

Sets up two handlers on the root logger:
- `StreamHandler` (console) at INFO level
- `RotatingFileHandler` → `APP_DIR / "qpopcv.log"` (1 MB max, 3 backups, UTF-8)

Format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`

---

## `qpopcv/config.py`

**Lines:** ~65

Central config constants and JSON load/save.

### Constants

| Name | Value | Description |
|------|-------|-------------|
| `APP_DIR` | `Path(sys.executable).parent` or `Path(__file__).parent` | Root dir (frozen vs source) |
| `MEDIA_DIR` | `_MEDIA_ROOT / "media"` | Built-in reference images |
| `FONTS_DIR` | `_MEDIA_ROOT / "fonts"` | Bundled font directory |
| `APP_VERSION` | `"1.2.3"` | Bumped on every code change |
| `BASE_CONFIG_PATH` | `APP_DIR / "config.json"` | Shared/repo config; never written by app |
| `USER_CONFIG_PATH` | `APP_DIR / "config.local.json"` | User settings; written by `save_config`; gitignored |
| `DISCORD_SERVER_URL` | `"https://discord.gg/KpupS6N3Zj"` | Community invite (permanent link) |
| `DEFAULT_CONFIG` | dict | Fallback values merged under both config files |

### `DEFAULT_CONFIG` keys

| Key | Default | Description |
|-----|---------|-------------|
| `webhook_url` | `""` | Discord webhook endpoint |
| `user_id` | `""` | 17–19-digit Discord snowflake |
| `check_interval` | `0.15` | Seconds between screen captures |
| `confidence` | `0.6` | Template match threshold (0–1) |
| `reference_image_paths` | `[]` | User's custom popup screenshots |
| `monitor_index` | `0` | Selected monitor (0 = primary) |
| `afk_notify` | `False` | Send AFK ping after 28 min |

### Functions

```python
def load_config() -> Dict[str, object]
```
Merges `DEFAULT_CONFIG` → `config.json` → `config.local.json`. Migrates legacy `reference_image_path` (str) to `reference_image_paths` (list).

```python
def save_config(config: Dict[str, object]) -> None
```
Writes to `config.local.json` only. Never touches `config.json`.

---

## `qpopcv/messages.py`

**Lines:** ~25

Timer delay constants and Discord message templates. Centralises all outgoing Discord message text so it can be changed without touching logic files.

### Timer constants

| Name | Value | Description |
|------|-------|-------------|
| `AFK_WARN_DELAY` | `28 * 60` (1680s) | Seconds before AFK warning fires |
| `AFK_LOGOUT_DELAY` | `2 * 60` (120s) | Seconds after warning before logout message |

### Message templates

| Name | Content | When sent |
|------|---------|-----------|
| `CONNECTED` | `"is connected <:verify:...>"` | Test button |
| `QUEUE_POP` | `"<a:queuepopblink:...> Q Pop!"` | Queue popup detected |
| `AFK_WARNING` | `"<:afkzzz:...> AFK 28m. Move character (2m until logout)"` | 28-min AFK warning |
| `AFK_LOGOUT` | `"<:logoutalert:...> Logged out!"` | 2-min escalation (no reset) |

All messages are sent as `<@user_id> <message>` by their callers.

---

## `qpopcv/metrics.py`

**Lines:** ~80

Persistent session metrics. Stores session history in `metrics.json` (next to the app executable) and computes aggregate stats on demand.

### `MetricsStore`

```python
class MetricsStore:
    def __init__(self, path: Path) -> None
```

Loads existing sessions from `path` on init. Each session is a dict:
```python
{
    "start": "<ISO datetime>",
    "end":   "<ISO datetime>",
    "duration_seconds": int,  # total elapsed minus AFK-paused time
    "detected": bool,         # True if session ended on a queue pop
}
```

#### Methods

```python
def record_session(start, end, duration_seconds, detected) -> Dict
```
Appends session to `self.sessions` and atomically saves to disk (write to `.tmp` then `os.replace`).

```python
def compute(day: Optional[date] = None) -> Dict
```
Aggregates all sessions (or only sessions on `day`) and returns:

| Key | Description |
|-----|-------------|
| `total_time_saved` | Sum of all session durations (seconds) |
| `effective_time_saved` | Sum of durations for sessions where `detected=True` |
| `pops_detected` | Count of detected sessions |
| `avg_queue_wait` | `effective_time_saved // pops_detected` (0 if no pops) |
| `longest_session` | Max single-session duration (seconds) |

---

## `qpopcv/app_ui.py`

**Lines:** ~385

Qt shell and HTTP server. Contains no business logic — all logic is in `api.py`.

### `_Handler(BaseHTTPRequestHandler)`

Handles all HTTP requests from the JS frontend.

- `do_GET` — serves static files from `qpopcv/static/`; handles `/events` SSE stream; path-traversal check via `relative_to()`
- `do_POST` — routes `/api/*` paths to `Api` methods; returns JSON
- `do_OPTIONS` — CORS preflight response
- `_handle_sse` — long-lived SSE connection; blocks on `event_queue.get(timeout=25)`; sends heartbeat on timeout; exits cleanly on `BrokenPipeError`/`ConnectionResetError`

### `_Bridge(QObject)`

Qt signal bus allowing HTTP server threads to safely call Qt main-thread operations.

| Signal | Purpose |
|--------|---------|
| `request_browse` | Opens `QFileDialog` on main thread |
| `request_quit` | Closes the application |
| `request_resize(int)` | Resizes window to content height |
| `request_minimize` | Minimizes window |
| `request_drag` | Starts native window drag |
| `request_flash` | Flashes taskbar icon (on AFK warning) |

### `_MainWindow(QMainWindow)`

Window subclass that dims to 50% opacity when unfocused (restores on focus) so it doesn't dominate secondary monitor attention.

### `QPopApp`

```python
class QPopApp:
    def __init__(self) -> None
    def run(self) -> None
```

#### Key Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `_api` | `Api` | Business logic instance |
| `_event_queue` | `queue.Queue` | Thread-safe SSE event buffer |
| `_bridge` | `_Bridge` | Qt signal bus |
| `_port` | `int` | Random free port for HTTP server |
| `_window` | `_MainWindow` | Frameless, always-on-top Qt window |
| `_view` | `QWebEngineView` | Renders the HTML/CSS/JS UI |

#### Key Methods

```python
def _start_http_server(self) -> ThreadingHTTPServer
```
Binds to `127.0.0.1:<random port>`, serves forever in a daemon thread.

```python
def _push_event(self, event_type: str, data: dict | None = None) -> None
```
Thread-safe SSE push. Puts `{"type": event_type, ...data}` on `_event_queue`. Also emits `request_flash` when `event_type == "afk_warning"`.

```python
def browse_image_sync(self) -> dict
```
Called from HTTP server thread. Emits `request_browse` signal → blocks on `threading.Event` until Qt main thread completes the file dialog (or 60s timeout).

```python
def resize_window(self, height: int) -> None
```
Emits `request_resize(height)` signal; Qt main thread adjusts window height.

---

## `qpopcv/api.py`

**Lines:** ~430

All application logic. Framework-agnostic — no Qt or HTTP imports. Receives a `push_event` callback for SSE and a `quit_fn` for shutdown.

### `Api`

```python
class Api:
    def __init__(self, config: Dict, push_event: Callable, quit_fn: Optional[Callable] = None)
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `config` | `dict` | Live config dict (mutated on save/start) |
| `_push` | `Callable` | SSE push callback |
| `_watcher` | `Optional[QPopWatcher]` | Active watcher, or None |
| `_afk_timer` | `Optional[threading.Timer]` | 28-min AFK warning timer |
| `_afk_escalation_timer` | `Optional[threading.Timer]` | 2-min post-warning logout timer |
| `_afk_warned` | `bool` | True if AFK warning is currently active |
| `_session_lock` | `threading.Lock` | Guards session time fields |
| `_session_start_time` | `Optional[datetime]` | Wall-clock session start |
| `_session_start_mono` | `Optional[float]` | Monotonic session start for duration |
| `_session_paused_at` | `Optional[float]` | Monotonic time when AFK pause started |
| `_session_paused_total` | `float` | Total paused seconds accumulated |
| `_metrics` | `MetricsStore` | Loads/saves `metrics.json` |
| `_update_info` | `Optional[UpdateInfo]` | Latest update check result |
| `_last_test_time` | `float` | Unix timestamp of last test ping |
| `update_manager` | `UpdateManager` | Update check/install coordinator |

#### Public Methods

```python
def get_initial_state(self) -> dict
```
Returns `{version, config, monitors, metrics}`. Metrics contains `all_time` and `today` computed dicts from `MetricsStore`.

```python
def start_watch(self, data: dict) -> dict
```
1. Validates webhook URL + user ID + reference image paths
2. If Discord.exe is running and `skip_discord_check` is False, returns `{"ok": False, "discord_running": True}`
3. Writes all fields to `self.config` and saves
4. Stops any existing watcher, creates and starts new `QPopWatcher`
5. Records session start time (wall clock + monotonic)
6. Cancels any existing AFK timers; arms new warning timer if `afk_notify=True`
7. Returns `{"ok": True, "warning": ...}` (warning if images are oversized)

```python
def stop_watch(self, detected: bool = False) -> dict
```
Stops watcher. Cancels both AFK timers. Calls `_end_session(detected)`. Returns `{"ok": True, "session": ...}`.

```python
def kill_discord(self) -> dict
```
Iterates `psutil.process_iter` for `discord.exe`, calls `terminate()` on each, waits up to 5s per process, then sleeps 3s (lets Discord's gateway detect the dropped connection before notifications are rerouted to mobile).

```python
def save_config_data(self, data: dict) -> dict
```
Saves all config fields without starting the watcher.

```python
def test_discord(self, data: dict) -> dict
```
Throttled (1s). Validates, calls `send_test_message`.

```python
def reset_afk(self) -> dict
```
Cancels `_afk_escalation_timer`. Resumes session clock (accumulates paused duration). Resets `_afk_warned`. Restarts 28-min AFK warning timer. Pushes `"afk_reset"` SSE event.

```python
def check_for_updates(self) -> None
def install_update(self) -> dict
```
Background threads. Push SSE events with progress.

#### Internal Methods

```python
def _on_detection(self) -> None
```
Called by `QPopWatcher` on detect. Calls `stop_watch(detected=True)` then pushes `"detected"` SSE event.

```python
def _send_afk_warning(self) -> None
```
Called by `_afk_timer` after 28 minutes. Sets `_afk_warned = True`. Pauses session clock. POSTs `AFK_WARNING` to Discord webhook. Pushes `"afk_warning"` SSE event. Arms `_afk_escalation_timer` (2 min).

```python
def _send_afk_logout(self) -> None
```
Called by `_afk_escalation_timer` 2 minutes after AFK warning (if not reset). POSTs `AFK_LOGOUT` to Discord webhook. Pushes `"afk_logout"` SSE event.

```python
def _end_session(self, detected: bool) -> Optional[dict]
```
Computes session duration (elapsed monotonic minus total paused time). Records to `MetricsStore`. Pushes `"metrics_update"` SSE event with refreshed all-time and today stats. Returns session dict.

```python
def _cleanup(self) -> None
```
Safety-net shutdown. Stops watcher and cancels both AFK timers.

---

## `qpopcv/watcher.py`

**Lines:** ~275

The screen detection engine. Runs entirely in a background daemon thread.

### `THROTTLE_SECONDS = 15`

Minimum seconds between successive Discord pings.

### `WatcherSettings`

```python
@dataclass
class WatcherSettings:
    webhook_url: str
    user_id: str
    check_interval: float = 0.5
    confidence: float = 0.6
    reference_image_paths: List[Path] = None
    monitor_index: int = 0

    @classmethod
    def from_config(cls, config: Dict) -> "WatcherSettings"
```

### `QPopWatcher`

```python
class QPopWatcher:
    def __init__(self, settings: WatcherSettings, on_detect: Optional[Callable] = None)
    def start(self) -> None
    def stop(self) -> None
    def is_running(self) -> bool
```

#### Internal State

| Attribute | Description |
|-----------|-------------|
| `_stop_event` | `threading.Event` — set by `stop()`, checked in `_loop()` |
| `_seen_once` | `bool` — tracks popup visible/not-visible transitions |
| `_last_qpop_time` | `float` — unix timestamp of last sent notification |
| `_region` | `(x, y, w, h)` — computed once at init from monitor selection |
| `_region_source` | `str` — human-readable monitor label for logging |
| `_reference_images` | `List[Tuple[str, Image.Image]]` — 0.9×/1.0×/1.1× variants |
| `oversized_refs` | `List[Path]` — refs that exceed the capture region (reported to UI) |

#### Key Methods

```python
def _prepare_reference_images(self) -> List[Tuple[str, Image.Image]]
```
Loads each user-configured path at 0.9×, 1.0×, 1.1× scales. Skips missing or oversized variants with warnings. If all variants of a path are oversized, adds it to `oversized_refs`. Returns empty list if no valid images.

```python
def _find_queue_popup(self, screenshot) -> Optional[str]
```
Iterates `_reference_images`, calls `pyautogui.locate(ref, screenshot, confidence=...)`. Returns match name or `None`.

```python
def _loop(self) -> None
```
Main loop: screenshot → find popup → state machine → `_stop_event.wait(interval)`. Catches all exceptions with a 2s retry wait.

```python
def _handle_detected_popup(self, match_name: str) -> None
```
Checks throttle. If not throttled: POSTs Discord webhook using `QUEUE_POP` message from `messages.py`, updates `_last_qpop_time`. Always calls `on_detect` callback regardless of throttle.

```python
def _send_discord_message(self, content: str) -> None
```
Direct `requests.post` with `timeout=5`.

---

## `qpopcv/discord_client.py`

**Lines:** ~23

Thin HTTP wrapper. Used only by the "Test Connection" button. The watcher and AFK timer call `requests.post` directly.

```python
def send_discord_mention(webhook_url, user_id, message, timeout=5.0) -> None
def send_test_message(webhook_url, user_id, timeout=5.0) -> None
```

---

## `qpopcv/validators.py`

**Lines:** ~72

Input validation. Used by `api.py`'s `_validate_discord()` and `_validate_ref_images()`.

```python
def validate_discord_core(webhook_url: str, user_id: str) -> bool
```
- Rejects empty or non-`https://discord.com/api/webhooks/` URLs
- Rejects empty or non-17–19-digit user IDs

```python
def validate_reference_image(path_str: str) -> bool
def validate_reference_images(paths: List[str]) -> bool
```
- Requires at least one non-empty, existing, non-directory path

---

## `qpopcv/monitor_utils.py`

Multi-monitor enumeration via `ctypes` (no extra dependencies).

```python
def get_monitors() -> List[Dict]
```
Returns list of `{x, y, w, h, is_primary}` dicts. Primary monitor first.

```python
def compute_top_center_region(monitor: Dict) -> Tuple[int, int, int, int]
```
Returns `(x + w//3, y, w//3, h//2)` — middle third, top half of the given monitor.

---

## `qpopcv/updater.py`

**Lines:** ~309

GitHub release checker and installer.

### `UpdateInfo` (dataclass)

```python
@dataclass
class UpdateInfo:
    available: bool
    current_version: str
    latest_version: str
    download_url: Optional[str]
    release_url: Optional[str]
    release_name: str = ""
    asset_digest: Optional[str] = None   # SHA-256 hex from GitHub API
```

### `UpdateManager`

```python
class UpdateManager:
    def __init__(self, repo_owner="Grymtrx", repo_name="QPopCV",
                 current_version="0.0.0", app_dir=None)
```

```python
def check_for_update(self, timeout=5.0) -> UpdateInfo
```
GETs GitHub releases API. Returns `UpdateInfo(available=False)` on any exception.

```python
def install_update(self, info: UpdateInfo, timeout=30.0) -> None
```
Downloads ZIP → verifies SHA-256 checksum (if `asset_digest` present) → extracts → frozen: write+launch `update.bat`; source: `_copy_tree()`.

`_copy_tree` skips `config.json` and hidden files to preserve user config.

---

## `qpopcv/static/index.html`

Single-page UI. Five tabs, one footer, one AFK banner.

### Tab structure

| Tab | ID | Contents |
|-----|----|----------|
| Discord | `tab-discord` | Webhook URL, User ID (password input + eye toggle), Test + Join Discord buttons |
| Capture | `tab-capture` | Monitor dropdown |
| Images | `tab-images` | Reference image rows (1–5) with browse/remove |
| AFK | `tab-afk` | `#afk-notify` checkbox + hint text |
| Metrics | `tab-metrics` | All Time / Today toggle; Total Time Saved hero; Effective Time Saved; Pops Detected / Avg Queue Wait / Longest Session stats |

### AFK Banner (inline, above footer)

Shown when AFK warning fires. Contains title, hint text, and "Reset AFK Timer" button (`#afk-reset-btn`). Hidden by default (`.hidden` class).

### Footer

| Element | Description |
|---------|-------------|
| `#watch-timer` | HH:MM:SS elapsed timer; shows "PAUSED" label during AFK warning; hidden when not watching |
| `.save-btn` | "Save Configuration" — triggers `/api/save_config` |
| `#discord-warn` | Discord running warning; "Continue Anyway" button; hidden by default |
| `.watch-btn` | "Watch" / "Stop" toggle — triggers `/api/start_watch` or `/api/stop_watch` |
| `.version-row` | Version label + update status (clickable when update available) |

---

## `qpopcv/static/style.css`

**Theme:** Pearl White (light glassmorphic, introduced v1.0.36)

All colors are CSS custom properties on `:root`. To retheme, only the `:root` block and a handful of component-specific `rgba()` values need changing.

| CSS Variable | Value | Purpose |
|---|---|---|
| `--glass-bg` | `#f4f6f9` | App background |
| `--glass-surface` | `rgba(255,255,255,0.70)` | Titlebar, footer |
| `--glass-raised` | `rgba(255,255,255,0.50)` | Input backgrounds |
| `--border` | `rgba(0,0,0,0.09)` | Standard borders |
| `--text` | `#111827` | Primary text |
| `--text-secondary` | `#374151` | Secondary text |
| `--text-muted` | `#6b7280` | Labels, hints |
| `--text-dim` | `#9ca3af` | Placeholders, dim icons |
| `--green` | `#16a34a` | Watch active / success |
| `--orange` | `#d97706` | Detected state |
| `--red` | `#dc2626` | Errors, close hover |
| `--discord` | `#5865f2` | Blurple accent (watch btn, tab underline, checkbox, logo dot) |

---

## `qpopcv/static/app.js`

**Lines:** ~680

Vanilla JS. Communicates with Python via `fetch('/api/...')` POSTs and `EventSource('/events')` SSE.

### State

```js
const state = {
  watching: false,          // is watcher running
  monitors: [],             // monitor label strings
  updateClickable: false,
  MAX_REFS: 5,
  metricsData: { all_time: null, today: null },
  metricsPeriod: 'all',     // 'all' or 'today'
  watchTimerInterval: null, // setInterval handle
  watchTimerSeconds: 0,     // elapsed seconds
  watchTimerPaused: false,  // true during AFK warning
};
```

### Key Functions

```js
function applyInitialState(data)
```
Populates all form controls from `data.config` on page load. Sets monitor dropdown, inputs, checkbox states, ref image rows. Calls `renderMetrics()` if `data.metrics` present.

```js
function collectFormData() -> object
```
Gathers all form values into `{webhook_url, user_id, reference_image_paths, monitor_index, afk_notify}`. Used by both Save and Watch Start.

```js
async function doStartWatch(skipDiscordCheck = false)
async function doStopWatch()
```
POST to `/api/start_watch` / `/api/stop_watch`. Handles `discord_running` response (shows Discord warning banner). Updates watch button state and starts/stops the watch timer.

```js
function handlePushEvent(event)
```
SSE event router. Dispatches to `onDetected()`, `onUpdateStatus()`, `onUpdateProgress()`, `onAfkWarning()`, `onAfkLogout()`, `onAfkReset()`, `onMetricsUpdate()`.

```js
function onDetected()
```
Stops watch timer, hides AFK banner, resets watch button to idle state, sets status pill to "Detected!", fires flash overlay animation.

```js
function startWatchTimer() / stopWatchTimer() / pauseWatchTimer() / resumeWatchTimer()
```
Manage the HH:MM:SS elapsed timer in the footer. `pauseWatchTimer` adds `.is-paused` class and shows "PAUSED" label; does not stop the interval (server-side session clock tracks effective time).

```js
function onAfkWarning()
```
Shows AFK banner, pauses watch timer display, sets status pill to "AFK Warning".

```js
function onAfkLogout()
```
Stops and hides watch timer, hides AFK banner, resets watch button to idle, sets status to "Stopped".

```js
function onAfkReset()
```
Hides AFK banner, resumes watch timer display, sets status to "Watching".

```js
function renderMetrics() / onMetricsUpdate(event)
```
Renders Metrics tab values from `state.metricsData` using `state.metricsPeriod` ('all' or 'today'). `onMetricsUpdate` updates the state cache then re-renders.

```js
function formatDuration(totalSeconds) -> string
```
Formats seconds as `Xd Xh Xm`, `Xh Xm`, `Xm Xs`, or `Xs`. Used for all metric time displays.

```js
function showToast(type, message, duration)
```
Creates animated toast notification (success / error / warning / info). Auto-dismisses after `duration` ms; click-to-dismiss also supported.

```js
function measureAndResize()
```
POSTs `app-card.offsetHeight` to `/api/resize` so the Qt window fits content exactly. Called after tab switches, AFK banner show/hide, and init.

---

## Data Flow Summary

```
User clicks Watch
    │
    ▼ collectFormData() → POST /api/start_watch
    │   {webhook_url, user_id, reference_image_paths, monitor_index, afk_notify}
    │
    ▼ Api.start_watch(data)
    │   validate → check Discord running → save to config.local.json
    │   → start QPopWatcher → record session start → arm AFK timer
    │
    ▼ QPopWatcher._loop() (daemon thread)
    │   pyautogui.screenshot(region)
    │   pyautogui.locate(reference, screenshot, confidence)
    │   → match found → requests.post(webhook, QUEUE_POP)
    │   → on_detect() → Api._on_detection()
    │       → stop_watch(detected=True) → _end_session()
    │       → push_event("detected")
    │
    ▼ SSE → EventSource → handlePushEvent({type:"detected"})
    │
    ▼ onDetected() → status pill "Detected!" + flash overlay + stop timer

28 minutes later (if afk_notify=True):
    ▼ threading.Timer fires _send_afk_warning()
    │   requests.post(webhook, AFK_WARNING)
    │   push_event("afk_warning") → JS shows AFK banner, pauses timer
    │   arms escalation timer (2 min)
    │
    User resets:
    ▼ /api/reset_afk → resume timer, restart 28-min AFK timer
    │
    OR 2 minutes later:
    ▼ _send_afk_logout() → requests.post(webhook, AFK_LOGOUT)
        push_event("afk_logout") → JS stops watch, resets to idle

Session ends:
    ▼ Api._end_session(detected)
        MetricsStore.record_session(...)
        push_event("metrics_update") → JS updates Metrics tab
```
