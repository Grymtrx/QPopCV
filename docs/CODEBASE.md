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
│   ├── discord_client.py                Discord HTTP wrapper
│   ├── watcher.py                       Detection engine
│   ├── validators.py                    Input validation
│   ├── updater.py                       Auto-updater
│   ├── theme.py                         Deprecated — CustomTkinter era artifact
│   ├── monitor_utils.py                 Multi-monitor enumeration + region math
│   ├── font_loader.py                   Font loading utility
│   └── static/
│       ├── index.html                   Single-page UI (4 tabs)
│       ├── style.css                    Pearl White glassmorphic theme
│       └── app.js                       Frontend logic
├── tests/
│   ├── conftest.py                      Pytest fixtures (Python 3.14 compat patches)
│   ├── test_api_afk.py                  AFK timer + notification tests
│   ├── test_config.py                   Config load/save tests
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
| `APP_VERSION` | `"1.0.38"` | Bumped on every code change |
| `BASE_CONFIG_PATH` | `APP_DIR / "config.json"` | Shared/repo config; never written by app |
| `USER_CONFIG_PATH` | `APP_DIR / "config.local.json"` | User settings; written by `save_config`; gitignored |
| `DISCORD_SERVER_URL` | `"https://discord.gg/KpupS6N3Zj"` | Community invite (permanent link) |
| `DEFAULT_CONFIG` | dict | Fallback values merged under both config files |

### `DEFAULT_CONFIG` keys

| Key | Default | Description |
|-----|---------|-------------|
| `webhook_url` | (hardcoded — see SEC-01) | Discord webhook endpoint |
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

## `qpopcv/app_ui.py`

**Lines:** ~300

Qt shell and HTTP server. Contains no business logic — all logic is in `api.py`.

### `_Handler(BaseHTTPRequestHandler)`

Handles all HTTP requests from the JS frontend.

- `do_GET` — serves static files from `qpopcv/static/`; handles `/events` SSE stream
- `do_POST` — routes `/api/*` paths to `Api` methods; returns JSON
- `_handle_sse` — long-lived SSE connection; blocks on `event_queue.get(timeout=25)`; sends heartbeat on timeout

### `_Bridge(QObject)`

Qt signal bus allowing HTTP server threads to safely call Qt main-thread operations.

| Signal | Purpose |
|--------|---------|
| `request_browse` | Opens `QFileDialog` on main thread |
| `request_quit` | Closes the application |
| `request_resize(int)` | Resizes window to content height |
| `request_minimize` | Minimizes window |
| `request_drag` | Starts native window drag |

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
| `_window` | `QMainWindow` | Frameless Qt window |
| `_view` | `QWebEngineView` | Renders the HTML/CSS/JS UI |

#### Key Methods

```python
def _start_http_server(self) -> ThreadingHTTPServer
```
Binds to `127.0.0.1:<random port>`, serves forever in a daemon thread.

```python
def _push_event(self, event_type: str, data: dict | None = None) -> None
```
Thread-safe SSE push. Puts `{"type": event_type, ...data}` on `_event_queue`.

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

**Lines:** ~230

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
| `_afk_timer` | `Optional[threading.Timer]` | AFK notification timer, or None |
| `_update_info` | `Optional[UpdateInfo]` | Latest update check result |
| `_last_test_time` | `float` | Unix timestamp of last test ping |
| `update_manager` | `UpdateManager` | Update check/install coordinator |

#### Public Methods

```python
def get_initial_state(self) -> dict
```
Returns `{version, config, monitors}`. Config includes all keys from `DEFAULT_CONFIG` plus monitor labels list.

```python
def start_watch(self, data: dict) -> dict
```
1. Validates webhook URL + user ID + reference image paths
2. Writes all fields (including `afk_notify`) to `self.config` and saves
3. Creates and starts `QPopWatcher`
4. Cancels any existing AFK timer, then arms a new one if `afk_notify=True`
5. Returns `{"ok": True, "warning": ...}` (warning if images are oversized)

```python
def stop_watch(self) -> dict
```
Stops watcher. Cancels and clears `_afk_timer`.

```python
def save_config_data(self, data: dict) -> dict
```
Saves all config fields without starting the watcher.

```python
def test_discord(self, data: dict) -> dict
```
Throttled (1s). Validates, calls `send_test_message`.

```python
def check_for_updates(self) -> None
def install_update(self) -> dict
```
Background threads. Push SSE events with progress.

#### Internal Methods

```python
def _on_detection(self) -> None
```
Called by `QPopWatcher` on detect. Pushes `"detected"` SSE event.

```python
def _send_afk_notification(self) -> None
```
Called by `threading.Timer` after 28 minutes. POSTs directly via `requests.post`:
```
<@user_id> Watch time nearing 30 minutes. Return to PC & move character to prevent blizzard auto-logout.
```
Returns early silently if `webhook_url` or `user_id` is empty. Catches all network exceptions and logs them. Sets `_afk_timer = None` on completion.

```python
def _cleanup(self) -> None
```
Safety-net shutdown. Stops watcher and cancels AFK timer.

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
| `_reference_images` | `List[Tuple[str, Image.Image]]` — 0.9×/1.0×/1.1× variants |
| `oversized_refs` | `List[Path]` — refs that exceed the capture region (reported to UI) |

#### Key Methods

```python
def _prepare_reference_images(self) -> List[Tuple[str, Image.Image]]
```
Loads each path at 0.9×, 1.0×, 1.1× scales. Skips missing or oversized variants with warnings.

```python
def _find_queue_popup(self, screenshot) -> Optional[str]
```
Iterates `_reference_images`, calls `pyautogui.locate(ref, screenshot, confidence=...)`. Returns match name or `None`.

```python
def _loop(self) -> None
```
Main loop: screenshot → find popup → state machine → `_stop_event.wait(interval)`.

```python
def _handle_detected_popup(self, match_name: str) -> None
```
Checks throttle. If not throttled: POSTs Discord webhook, updates `_last_qpop_time`. Always calls `on_detect` callback.

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

Input validation. Used by `api.py`'s `_validate_discord()` and `_validate_ref_images()` (internal functions, same logic reused from here in tests).

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
Downloads ZIP → extracts → frozen: write+launch `update.bat`; source: `_copy_tree()`.

`_copy_tree` skips `config.json` and hidden files to preserve user config.

---

## `qpopcv/static/index.html`

Single-page UI. Four tabs, one footer.

### Tab structure

| Tab | ID | Contents |
|-----|----|----------|
| Discord | `tab-discord` | Webhook URL, User ID, Test + Join Discord buttons |
| Capture | `tab-capture` | Monitor dropdown |
| Images | `tab-images` | Reference image rows (1–5) with browse/remove |
| AFK | `tab-afk` | `#afk-notify` checkbox + hint text |

### Footer

| Element | Description |
|---------|-------------|
| `.save-btn` | "Save Configuration" — triggers `/api/save_config` |
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

**Lines:** ~470

Vanilla JS. Communicates with Python via `fetch('/api/...')` POSTs and `EventSource('/events')` SSE.

### State

```js
const state = {
  watching: false,     // is watcher running
  monitors: [],        // monitor label strings
  updateClickable: false,
  MAX_REFS: 5,
};
```

### Key Functions

```js
function applyInitialState(data)
```
Populates all form controls from `data.config` on page load. Sets monitor dropdown, inputs, checkbox states, ref image rows.

```js
function collectFormData() -> object
```
Gathers all form values into `{webhook_url, user_id, reference_image_paths, monitor_index, afk_notify}`. Used by both Save and Watch Start.

```js
async function doStartWatch()
async function doStopWatch()
```
POST to `/api/start_watch` / `/api/stop_watch`. Update watch button state.

```js
function handlePushEvent(event)
```
SSE event router. Dispatches to `onDetected()`, `onUpdateStatus()`, `onUpdateProgress()`.

```js
function onDetected()
```
Flashes status pill to "Detected!", adds `.detected-overlay` flash animation.

```js
function showToast(type, message, duration)
```
Creates animated toast notification (success / error / warning / info).

```js
function measureAndResize()
```
POSTs `document.documentElement.scrollHeight` to `/api/resize` so the Qt window fits content exactly. Called after tab switches and after init.

---

## Data Flow Summary

```
User clicks Watch
    │
    ▼ collectFormData() → POST /api/start_watch
    │   {webhook_url, user_id, reference_image_paths, monitor_index, afk_notify}
    │
    ▼ Api.start_watch(data)
    │   validate → save to config.local.json → start QPopWatcher → arm AFK timer
    │
    ▼ QPopWatcher._loop() (daemon thread)
    │   pyautogui.screenshot(region)
    │   pyautogui.locate(reference, screenshot, confidence)
    │   → match found → requests.post(webhook, "<@user_id> Your Queue has popped!")
    │   → Api._on_detection() → push_event("detected")
    │
    ▼ SSE → EventSource → handlePushEvent({type:"detected"})
    │
    ▼ onDetected() → status pill flash + overlay animation

28 minutes later (if afk_notify=True):
    ▼ threading.Timer fires _send_afk_notification()
        requests.post(webhook, "<@user_id> Watch time nearing 30 minutes...")
```
