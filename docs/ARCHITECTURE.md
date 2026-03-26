# QPopCV — Architecture Overview

> **Purpose of this document:** High-level map of how QPopCV works, intended as a starting-point context for Claude (or any developer) picking up this codebase.

---

## What is QPopCV?

A lightweight Windows desktop app that watches the screen for a World of Warcraft Solo Shuffle queue popup and fires a Discord webhook notification (with a user mention) the moment it appears. Users can step away from their PC while queuing, and be pinged on phone or desktop Discord. All while stayin within Blizzards TOS.

**Current version:** `1.0.10`
**Target OS:** Windows (uses `pyautogui`, `os.startfile`, batch scripts)

---

## Module Map

| File                       | Role                                                                 |
| -------------------------- | -------------------------------------------------------------------- |
| `main.py`                  | Entry point — configures logging, creates `QPopApp`, starts mainloop |
| `qpopcv/__init__.py`       | Re-exports `QPopApp`                                                 |
| `qpopcv/app_ui.py`         | All GUI logic (`QPopApp` class, CustomTkinter)                       |
| `qpopcv/watcher.py`        | Screen detection engine (`QPopWatcher`, `WatcherSettings`)           |
| `qpopcv/config.py`         | Config constants, `load_config`, `save_config`                       |
| `qpopcv/discord_client.py` | Thin wrapper around Discord webhook HTTP calls                       |
| `qpopcv/validators.py`     | Input validation (webhook, user ID, reference image path)            |
| `qpopcv/theme.py`          | UI color constants (Tailwind-inspired palette)                       |
| `qpopcv/updater.py`        | GitHub release checker and installer (`UpdateManager`, `UpdateInfo`) |

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────┐
│                   main.py                       │
│  configure logging → QPopApp() → app.run()      │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│              QPopApp  (app_ui.py)               │
│                                                 │
│  ┌─────────┐  ┌──────────┐  ┌───────────────┐   │
│  │ config  │  │validators│  │  theme colors │   │
│  └─────────┘  └──────────┘  └───────────────┘   │
│                                                 │
│ Buttons: Save │ Test │ Watch │ Discord │ Update │
└─────┬───────────────────────┬───────────────────┘
      │                       │
      ▼ (background thread)   ▼ (background thread)
┌──────────────┐       ┌──────────────────────┐
│ QPopWatcher  │       │   UpdateManager      │
│ (watcher.py) │       │   (updater.py)       │
│              │       │                      │
│ screenshot() │       │ GitHub API → latest  │
│ locate()     │       │ download + bat script│
│ → Discord    │       └──────────────────────┘
└──────────────┘
      │
      ▼
┌──────────────────┐
│ discord_client   │
│ POST webhook URL │
└──────────────────┘
```

---

## Threading Model

```
Main Thread (Tkinter mainloop)
│
├─► Update Check Thread (daemon)
│     Spawned once on startup (after 250ms delay)
│     check_for_update() → GitHub API
│     Result posted back via root.after(0, callback)
│
├─► Watcher Thread (daemon)
│     Spawned on "Watch" button click
│     Runs _loop() until _stop_event is set
│     Communicates back to GUI via on_detect callback (→ root.after)
│
└─► Update Install Thread (daemon)
      Spawned only if user clicks "install update"
      Downloads ZIP, extracts, launches update.bat, then calls on_close()
```

**Thread safety notes:**
- Watcher communicates back to Tkinter only via `on_detect` callback, which calls `status_label.after(1600, restore)` — safe.
- `_seen_once` and `_last_qpop_time` are accessed only from the watcher thread — no lock needed.
- All `root.after(0, ...)` calls ensure UI updates happen on the main thread.

---

## Detection Algorithm

```
Every check_interval seconds (default 0.15s):
│
├── 1. pyautogui.screenshot(region=top_center_third)
│         region = (screen_w//3, 0, screen_w//3, screen_h//2)
│
├── 2. For each reference image variant (90%, 100%, 110% scale):
│         pyautogui.locate(reference, screenshot, confidence=0.6)
│
├── 3. State machine:
│         popup appeared (not seen → seen):
│           → _handle_detected_popup()
│               → check 15s throttle
│               → POST Discord webhook
│               → call on_detect() for GUI flash
│         popup gone (seen → not seen):
│           → reset _seen_once = False
│
└── 4. Wait check_interval, repeat
```

**Reference image loading:**
- If `reference_image_path` is set in config → load that image at 3 scales (0.9×, 1.0×, 1.1×)
- If not set → detection is disabled (no built-in fallbacks as of current version)

---

## Config Data Flow

```
config.json (on disk)
    │
    ▼
load_config()  ← merges over DEFAULT_CONFIG
    │
    ▼
QPopApp.config dict  ←→  UI StringVars (webhook_var, user_var, ref_var)
    │
    ├─ on_save() → validate → save_config() → write config.json
    └─ _start_watch() → WatcherSettings.from_config() → QPopWatcher
```

**Config keys:**

| Key                    | Type  | Default                        | Description                                  |
| ---------------------- | ----- | ------------------------------ | -------------------------------------------- |
| `webhook_url`          | str   | (hardcoded — see KNOWN_ISSUES) | Discord webhook endpoint                     |
| `user_id`              | str   | `""`                           | 17–19-digit Discord snowflake ID             |
| `check_interval`       | float | `0.15`                         | Seconds between screen captures              |
| `confidence`           | float | `0.6`                          | Template match confidence threshold (0–1)    |
| `reference_image_path` | str   | `""`                           | Path to user's custom queue popup screenshot |

---

## Update Mechanism

```
Startup (250ms delay)
    │
    └─► check_for_update()
            GET https://api.github.com/repos/Grymtrx/QPopCV/releases/latest
            Compare tag_name vs APP_VERSION ("1.0.10")
            → UpdateInfo { available, latest_version, download_url }

User clicks "Update available: x.x.x"
    │
    └─► install_update(info)
            Download .zip from GitHub release assets → temp dir
            Extract zip

            If frozen (.exe):
                Write update.bat to temp dir
                os.startfile(update.bat)   ← runs after this process exits
                app closes → bat waits for exe → xcopy → restart exe

            If source:
                _copy_tree() → directly overwrites files in app_dir
                (skips config.json and hidden files)
```

---

## Key Constants

| Constant             | Location        | Value                    | Description                       |
| -------------------- | --------------- | ------------------------ | --------------------------------- |
| `THROTTLE_SECONDS`     | `watcher.py:14` | `15`                     | Min seconds between watcher Discord pings |
| `TEST_THROTTLE_SECONDS`| `app_ui.py:21`  | `1`                      | Min seconds between test button pings     |
| `APP_VERSION`          | `config.py:18`  | `"1.0.10"`               | Current version string                    |
| `CONFIG_PATH`        | `config.py:19`  | `<app_dir>/config.json`  | Config file location              |
| `DISCORD_SERVER_URL` | `config.py:20`  | Discord invite           | Community Discord link            |
| `GITHUB_API`         | `updater.py:19` | GitHub releases endpoint | Update check URL template         |
| `MEDIA_DIR`          | `config.py:14`  | `<_MEDIA_ROOT>/media/`   | Built-in reference images         |

---

## External Dependencies

| Package         | Used For                                        | Notes                                        |
| --------------- | ----------------------------------------------- | -------------------------------------------- |
| `customtkinter` | GUI framework                                   | Modern Tkinter widgets                       |
| `pyautogui`     | Screenshot + template matching                  | `locate()`, `screenshot()`, `size()`         |
| `Pillow`        | Image loading and scaling                       | `Image.open`, `Image.resize`                 |
| `requests`      | Discord webhooks + GitHub API + update download | All HTTP calls                               |
