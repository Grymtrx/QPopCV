# AFK Tab — Design Spec
Date: 2026-03-26

## Overview

Add an "AFK" tab to QPopCV that lets users opt in to a Discord notification after 28 minutes of continuous watch time. The notification reminds them to return to their PC and move their character to prevent Blizzard's auto-logout.

---

## Frontend (HTML/CSS/JS)

### Tab bar
Add a fourth tab button `AFK` after `Images` in the tab bar (`index.html`).

### AFK tab panel
Single checkbox row:

```
[ ] Enable AFK notification (fires at 28 min)
```

- Checkbox ID: `afk-notify`
- Label: "Enable AFK notification"
- Subtext below the checkbox (muted): "Sends a Discord ping after 28 minutes to prevent Blizzard auto-logout"

### State integration (`app.js`)
- On `loadInitialState`: read `config.afk_notify` and set the checkbox
- On Save: include `afk_notify: afkNotifyCheckbox.checked` in the save payload
- On Watch start: include `afk_notify: afkNotifyCheckbox.checked` in the start payload
- No SSE event needed — the notification fires silently via Discord

---

## Config

New key in `DEFAULT_CONFIG` (`config.py`):

```python
"afk_notify": False,
```

Flows through all three config touch-points:
- `get_initial_state()` — returns `afk_notify` in the `config` dict
- `save_config_data()` — reads and persists `afk_notify`
- `start_watch()` — reads `afk_notify` to decide whether to arm the timer

---

## Backend (`api.py`)

### New instance variable
```python
self._afk_timer: Optional[threading.Timer] = None
```

### `start_watch()` change
After the watcher is started successfully, if `afk_notify` is `True`:
```python
self._afk_timer = threading.Timer(28 * 60, self._send_afk_notification)
self._afk_timer.daemon = True
self._afk_timer.start()
```
Store `afk_notify` so `_send_afk_notification` can use the current `user_id`.

### `stop_watch()` change
```python
if self._afk_timer:
    self._afk_timer.cancel()
    self._afk_timer = None
```

### New method `_send_afk_notification()`
Sends a Discord POST directly via `requests`:

```python
def _send_afk_notification(self) -> None:
    webhook_url = str(self.config.get("webhook_url", "")).strip()
    user_id = str(self.config.get("user_id", "")).strip()
    if not webhook_url or not user_id:
        return
    content = (
        f"<@{user_id}> Watch time nearing 30 minutes. "
        "Return to PC & move character to prevent blizzard auto-logout."
    )
    try:
        requests.post(webhook_url, json={"content": content}, timeout=5)
    except Exception as exc:
        logger.error("AFK notification failed: %s", exc)
    self._afk_timer = None
```

---

## Error handling

- If the timer fires but `webhook_url` or `user_id` is empty, it exits silently (logged at debug level).
- Network errors are caught and logged; no retry — this is best-effort.
- Stopping the watcher before 28 minutes always cancels the timer.

---

## Out of scope

- No repeat notifications within the same session.
- No UI indicator showing remaining time.
- No toasting in the app UI when the AFK notification fires.
