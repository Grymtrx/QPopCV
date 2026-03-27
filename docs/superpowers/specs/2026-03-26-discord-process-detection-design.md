# Discord Process Detection Design

**Date:** 2026-03-26
**Status:** Approved

## Context

QPopCV sends Discord webhook notifications when a queue pop is detected (image match) or after 28 minutes of AFK watching. If the user has Discord running on their PC (system tray), those notifications are delivered locally — not to their phone — defeating the entire purpose of stepping away. Users were reporting "it doesn't work" without realizing they needed to quit Discord first.

This feature detects whether Discord is running at watch-start time, warns the user, and offers a one-click kill option.

---

## Behaviour

- When the user clicks **Watch**, the backend checks for a running `Discord.exe` process before starting the watcher.
- If Discord **is not running**: watch starts immediately, no friction.
- If Discord **is running**: watch does NOT start. An inline warning banner appears above the Watch button with two actions:
  - **Kill Discord** — terminates all `Discord.exe` processes, hides the banner, starts the watcher.
  - **Continue Anyway** — starts the watcher with Discord still running (user's choice, no further nag).
- If the kill fails (e.g., permission error): an error toast is shown and the banner stays visible.

The check is unconditional — it does not depend on the AFK checkbox state, because queue pop notifications are also routed through Discord webhook and have the same problem.

---

## Components

### Backend (`qpopcv/api.py`)

**`api.start_watch(data)`** — add `skip_discord_check` boolean field (default `false`):
- If `false` and `Discord.exe` is detected running → return `{"ok": false, "discord_running": true}` (no error string; frontend handles messaging).
- Otherwise proceed as normal.

**`api.kill_discord()`** — new method:
- Uses `psutil` to iterate processes, terminate all named `Discord.exe`.
- Returns `{"ok": true}` on success, `{"ok": false, "error": "<reason>"}` on failure.

**New route `/api/kill_discord`** registered in `app_ui.py`'s `do_POST` handler.

### Frontend (`qpopcv/static/`)

**`index.html`** — new inline banner element (hidden by default) inserted above the Watch button in the footer:
```html
<div class="discord-warn hidden" id="discord-warn">
  <span class="discord-warn-msg">
    ⚠ Discord is running. To receive notifications on your phone,
    quit Discord here or from the system tray.
  </span>
  <div class="discord-warn-actions">
    <button id="discord-kill-btn">Kill Discord</button>
    <button id="discord-continue-btn">Continue Anyway</button>
  </div>
</div>
```

**`app.js`** — changes to `doStartWatch()`:
- On `discord_running: true` response → show banner, re-enable Watch button (user must act).
- "Kill Discord" click → POST `/api/kill_discord` → on success hide banner, call `doStartWatch({ skip_discord_check: true })` → on failure show error toast.
- "Continue Anyway" click → hide banner, call `doStartWatch({ skip_discord_check: true })`.

**`style.css`** — new `.discord-warn` styles matching the existing Pearl White glassmorphic theme (warning amber tones, consistent with `.toast-warning` palette).

### Dependencies (`requirements.txt`)

Add `psutil` — used for process enumeration and termination. Already present as a transitive dependency in `_internal/`; needs explicit declaration for `pip install` users.

---

## Data Flow

```
User clicks Watch
      │
      ▼
POST /api/start_watch  {skip_discord_check: false, ...formData}
      │
      ├─ Discord.exe NOT running → {ok: true}  →  watch starts, no banner
      │
      └─ Discord.exe running    → {ok: false, discord_running: true}
              │
              ├─ User clicks "Kill Discord"
              │         POST /api/kill_discord
              │         ├─ success → hide banner → POST /api/start_watch {skip_discord_check: true}
              │         └─ failure → error toast, banner stays
              │
              └─ User clicks "Continue Anyway"
                        hide banner → POST /api/start_watch {skip_discord_check: true}
```

---

## Files Changed

| File | Change |
|------|--------|
| `requirements.txt` | Add `psutil` |
| `qpopcv/api.py` | Add `skip_discord_check` param to `start_watch`; add `kill_discord()` method |
| `qpopcv/app_ui.py` | Register `/api/kill_discord` route |
| `qpopcv/static/index.html` | Add `#discord-warn` banner element in footer |
| `qpopcv/static/app.js` | Handle `discord_running` response; wire Kill/Continue buttons |
| `qpopcv/static/style.css` | Add `.discord-warn` styles |
| `qpopcv/config.py` | Bump `APP_VERSION` to `1.0.40` |

---

## Verification

1. Run `python main.py` with Discord open in the system tray.
2. Click **Watch** — banner should appear, Watch button re-enabled, watch NOT started.
3. Click **Kill Discord** — Discord closes, watch starts, banner disappears.
4. Re-run with Discord open, click **Watch**, click **Continue Anyway** — watch starts, banner disappears.
5. Run with Discord closed — click **Watch** — watch starts immediately with no banner.
6. Confirm `psutil` is importable: `python -c "import psutil; print(psutil.__version__)"`.
