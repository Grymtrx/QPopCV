# QPopCV — Codebase Reference

> **Purpose of this document:** Per-file breakdown of every module — classes, functions, data structures, and notable implementation details. Use this as a code map when making targeted changes.

---

## Directory Tree

```
QPopCV/
├── main.py                          Entry point
├── requirements.txt                 Python dependencies
├── pyproject.toml                   Build config (PyInstaller packaging)
├── docs/
│   ├── ARCHITECTURE.md              System overview + diagrams
│   ├── CODEBASE.md                  (this file)
│   └── KNOWN_ISSUES.md              Bugs, security issues, tech debt
├── qpopcv/                          Main package
│   ├── __init__.py                  Re-exports QPopApp
│   ├── app_ui.py                    GUI (507 lines)
│   ├── config.py                    Config management (37 lines)
│   ├── config.json                  Runtime config (user-editable)
│   ├── discord_client.py            Discord HTTP wrapper (23 lines)
│   ├── watcher.py                   Detection engine (255 lines)
│   ├── validators.py                Input validation (50 lines)
│   ├── theme.py                     Color constants (12 lines)
│   ├── updater.py                   Auto-updater (309 lines)
│   └── media/
│       ├── qpop_ss_blizzardUI_reference.png   Built-in reference (Blizzard UI)
│       ├── qpop_ss_bbq_reference.png          Built-in reference (BBQ UI)
│       ├── qpop_ss_bbq_dark_reference.png     Built-in reference (BBQ UI dark)
│       ├── Dialog Placement.png               Documentation screenshot
│       ├── MobileNoti.png                     Documentation screenshot
│       └── icon/                              App icons
├── tests/
│   ├── QpopCV_prototype.py          Original single-file prototype (not automated tests)
│   └── test_capture_region.py       Manual region capture utility
└── tools/
    ├── show_watch_region.py         Visualizes the watch region on screen
    └── privacy_mask.py              Transparent overlay for safe screenshotting
```

---

## `main.py`

**Lines:** 28

Entry point. Configures logging and starts the app.

```python
def main() -> None
```

Sets up two handlers on the root logger (both using format `%(asctime)s [%(levelname)s] %(name)s: %(message)s`):
- `StreamHandler` (console) via `logging.basicConfig` at INFO level
- `RotatingFileHandler` → `APP_DIR / "qpopcv.log"` (1 MB max, 3 backups, UTF-8)

---

## `qpopcv/config.py`

**Lines:** 44

Central config constants and JSON load/save. Single source of truth for path resolution (frozen vs source).

### Constants

| Name | Value | Description |
|------|-------|-------------|
| `APP_DIR` | `Path(sys.executable).parent` or `Path(__file__).parent` | Root dir (frozen vs source) |
| `_MEDIA_ROOT` | `sys._MEIPASS` (frozen) or `APP_DIR` (source) | Base for media assets; uses PyInstaller's temp dir when frozen onefile |
| `MEDIA_DIR` | `_MEDIA_ROOT / "media"` | Built-in reference image directory |
| `APP_VERSION` | `"1.0.10"` | Bumped for releases |
| `CONFIG_PATH` | `APP_DIR / "config.json"` | Config file path |
| `DISCORD_SERVER_URL` | `"https://discord.gg/KpupS6N3Zj"` | Community invite (permanent link) |
| `DEFAULT_CONFIG` | dict | Fallback values when config.json missing or corrupt |

### Functions

```python
def load_config() -> Dict[str, object]
```
Reads `config.json`, merges over `DEFAULT_CONFIG`. On any read/parse error logs `logger.warning("Failed to load config, using defaults: %s", exc)` and returns `DEFAULT_CONFIG.copy()`.

```python
def save_config(config: Dict[str, object]) -> None
```
Serialises the dict as indented JSON and writes to `CONFIG_PATH`. No error handling.

---

## `qpopcv/app_ui.py`

**Lines:** 507

All GUI code. Built with `customtkinter` (CTk). Uses a single `card` frame inside a `CTk` root window (360×220 min size).

### Class `QPopApp`

```python
class QPopApp:
    def __init__(self) -> None
    def run(self) -> None
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `config` | `Dict[str, object]` | Loaded config dict |
| `_watcher` | `Optional[QPopWatcher]` | Active watcher instance (or None) |
| `_update_info` | `Optional[UpdateInfo]` | Latest update check result |
| `_update_clickable` | `bool` | Whether version label is clickable |
| `_last_test_time` | `float` | Unix timestamp of last test message (throttle) |
| `update_manager` | `UpdateManager` | Update check/install coordinator |
| `webhook_var` | `ctk.StringVar` | Bound to webhook URL entry |
| `user_var` | `ctk.StringVar` | Bound to user ID entry |
| `ref_var` | `ctk.StringVar` | Bound to reference image path entry |
| `status_label` | `ctk.CTkLabel` | Shows ● Stopped / ● Watching / ● Detected! |
| `version_and_update` | `ctk.CTkLabel` | Shows version + update status (clickable) |

#### UI Layout (grid rows inside `card` frame)

| Row | Content |
|-----|---------|
| 0 | Discord Webhook label + entry |
| 1 | Discord User ID label + entry |
| 2 | Reference Image label + entry + "Add" button |
| 3 | Button row: Discord | Test Connection | Save Config | Watch |
| 4 | Status label (centered) + Version/update label |

#### Key Methods

```python
def _build_ui(self) -> None
```
Constructs all widgets. Called once from `__init__`.

```python
def _set_status(self, text: str, color: str) -> None
def _flash_detected_status(self) -> None
```
Status label helpers. `_flash_detected_status` shows "● Detected!" for 1.6s then restores previous state.

```python
def _update_config_from_ui(self) -> None
```
Pulls current StringVar values into `self.config`. Called before save and before starting watcher.

```python
def on_save(self) -> None
```
Validates via `validate_discord_core` + `validate_reference_image`, then calls `save_config`.

```python
def on_test_discord(self) -> None
```
Checks 1s throttle (`TEST_THROTTLE_SECONDS`), validates inputs, calls `send_test_message`. Shows result dialog.

```python
def on_toggle_watch(self) -> None
def _start_watch(self) -> None
def _stop_watch(self) -> None
```
Start/stop toggle. `_start_watch` validates, saves config, shows mobile-Discord info dialog, creates `QPopWatcher`, calls `watcher.start()`.

```python
def _start_update_check(self) -> None
```
Spawns daemon thread → `check_for_update()` → posts result back via `root.after`.

```python
def on_update_click(self, _event=None) -> None
def _perform_update_install(self) -> None
def _restart_after_update(self) -> None
```
Update installation flow. `_perform_update_install` runs in daemon thread, posts status back to main thread on completion or failure.

```python
def on_close(self) -> None
```
Stops watcher, destroys root window.

---

## `qpopcv/watcher.py`

**Lines:** 249

The screen detection engine. Runs entirely in a background daemon thread.

### `THROTTLE_SECONDS = 15`

Minimum seconds between successive Discord pings for the same user.

### `MEDIA_DIR`

Imported from `config.py`. Points to `qpopcv/media/` (frozen `.exe` and source contexts handled there).

### Dataclass `WatcherSettings`

```python
@dataclass
class WatcherSettings:
    webhook_url: str
    user_id: str
    check_interval: float = 0.5
    confidence: float = 0.6
    reference_image_path: Optional[Path] = None

    @classmethod
    def from_config(cls, config: Dict[str, object]) -> "WatcherSettings"
```

`from_config` converts the loose `dict` from `load_config()` into a typed dataclass. Handles empty `reference_image_path` → `None`.

### Class `QPopWatcher`

```python
class QPopWatcher:
    def __init__(self, settings: WatcherSettings, on_detect: Optional[Callable[[], None]] = None)
    def start(self) -> None
    def stop(self) -> None
    def is_running(self) -> bool
```

#### Internal State

| Attribute | Description |
|-----------|-------------|
| `_stop_event` | `threading.Event` — set by `stop()`, checked in `_loop()` |
| `_seen_once` | `bool` — tracks popup visible/not-visible state transitions |
| `_last_qpop_time` | `float` — unix timestamp of last sent notification |
| `_region` | `(x, y, w, h)` — computed once at init |
| `_reference_images` | `List[Tuple[str, Image.Image]]` — loaded once at init |

#### Key Methods

```python
@staticmethod
def _compute_top_center_region() -> Tuple[int, int, int, int]
```
Returns `(screen_w//3, 0, screen_w//3, screen_h//2)` — middle third of screen, top half.

```python
def _prepare_reference_images(self) -> List[Tuple[str, Image.Image]]
```
Loads user reference image at 0.9×, 1.0×, 1.1× scales. Returns empty list if no valid path (disables detection).

```python
def _find_queue_popup(self, screenshot) -> Optional[str]
```
Iterates `_reference_images`, calls `pyautogui.locate(ref, screenshot, confidence=...)`. Returns match name or `None`.

```python
def _loop(self) -> None
```
Main loop: screenshot → find popup → state machine → sleep via `_stop_event.wait(interval)`.

```python
def _handle_detected_popup(self, match_name: str) -> None
```
Checks throttle. If not throttled: calls `_send_discord_message`, updates `_last_qpop_time`. Always calls `on_detect` callback.

```python
def _send_discord_message(self, content: str) -> None
```
Direct `requests.post` to `_webhook_url` with `timeout=5`. No error handling beyond outer `except Exception`.

---

## `qpopcv/discord_client.py`

**Lines:** 23

Thin HTTP wrapper. Used only by the GUI's "Test Connection" button.
(The watcher calls `requests.post` directly in `_send_discord_message`.)

```python
def send_discord_mention(webhook_url: str, user_id: str, message: str, timeout: float = 5.0) -> None
```
POSTs `{"content": "<@user_id> message"}` to the webhook URL.

```python
def send_test_message(webhook_url: str, user_id: str, timeout: float = 5.0) -> None
```
Calls `send_discord_mention` with the message `"connected ✅"`.

---

## `qpopcv/validators.py`

**Lines:** 50

Input validation functions. Each shows a `messagebox` on failure and returns `bool`.

```python
def validate_discord_core(webhook_url: str, user_id: str) -> bool
```
- Rejects empty webhook URL
- Rejects URL that does not start with `https://discord.com/api/webhooks/`
- Rejects empty user ID
- Rejects user ID that is not 17–19 digits (covers old accounts and 19-digit snowflakes)

```python
def validate_reference_image(path_str: str) -> bool
```
- Rejects empty path
- Rejects non-existent path
- Rejects directories


---

## `qpopcv/updater.py`

**Lines:** 309

GitHub release checker and installer.

### Dataclass `UpdateInfo`

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

### Class `UpdateManager`

```python
class UpdateManager:
    def __init__(self, repo_owner="Grymtrx", repo_name="QPopCV",
                 current_version="0.0.0", app_dir=None)
```

#### Public API

```python
def check_for_update(self, timeout: float = 5.0) -> UpdateInfo
```
GET `https://api.github.com/repos/Grymtrx/QPopCV/releases/latest`. Compares `tag_name` to `current_version`. Returns `UpdateInfo(available=False)` on any exception (silent).

```python
def install_update(self, info: UpdateInfo, timeout: float = 30.0) -> None
```
1. `tempfile.mkdtemp()` → download ZIP → extract
2. Frozen: write + launch `update.bat` (waits for exe exit → xcopy → restart)
3. Source: `_copy_tree()` directly

#### Internal Helpers

```python
@staticmethod def _normalize_tag(tag: str) -> str
@staticmethod def _normalize_version(version: str) -> Sequence
def _is_newer_version(self, latest: str, current: str) -> bool
@staticmethod def _select_download_url(data: dict) -> Optional[str]
@staticmethod def _download_file(url: str, dest: Path, timeout: float) -> None
@staticmethod def _find_source_root(extract_dir: Path) -> Path
def _copy_tree(self, src: Path, dest: Path) -> None
def _run_external_updater(self, source_root: Path, tmp_dir: Path) -> None
```

`_copy_tree` explicitly skips `config.json` and `.`-prefixed files to preserve user config during source updates.

`_run_external_updater` writes a batch script to `tmp_dir/qpopcv_update.bat` and launches it with `os.startfile()`. The script: waits for exe to exit via `tasklist`, `xcopy`s files, restarts exe, cleans temp dir.

---

## `qpopcv/theme.py`

**Lines:** 12

Color constants, Tailwind CSS palette inspired.

| Constant | Hex | Used For |
|----------|-----|----------|
| `BG_COLOR` | `#e5e7eb` | Window background |
| `CARD_BG` | `#f9fafb` | Card frame background |
| `CARD_BORDER` | `#d1d5db` | Card border |
| `ACCENT` | `#0ea5e9` | Primary buttons, update text |
| `ACCENT_HOVER` | `#0284c7` | Button hover state |
| `TEXT_PRIMARY` | `#111827` | Labels, entry text |
| `TEXT_MUTED` | `#6b7280` | Secondary text, version label |
| `DANGER` | `#dc2626` | Stopped status, errors |
| `SUCCESS` | `#16a34a` | Watching status |
| `DETECTED` | `#f97316` | Flash on queue pop detection |

---

## Data Flow Summary

```
User input (GUI StringVars)
    │
    ▼ on_save() / _start_watch()
validate_discord_core() + validate_reference_image()
    │
    ▼
_update_config_from_ui() → self.config dict
    │
    ├──► save_config() → config.json
    │
    └──► WatcherSettings.from_config(self.config)
              │
              ▼
         QPopWatcher(settings, on_detect=_flash_detected_status)
              │
              ▼ (daemon thread: _loop)
         pyautogui.screenshot(region)
              │
              ▼
         pyautogui.locate(reference, screenshot, confidence)
              │  match found
              ▼
         requests.post(webhook_url, {"content": "<@user_id> Your Queue has popped!"})
              │
              ▼
         on_detect() → root.after → status_label flash
```
