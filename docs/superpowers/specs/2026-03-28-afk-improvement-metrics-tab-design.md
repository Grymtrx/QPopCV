# AFK Notification Improvement & Metrics Tab

**Date:** 2026-03-28
**Version target:** 1.2.0

## Overview

Two features that share underlying infrastructure (session tracking, watch timer):

1. **Improved AFK Notification** — in-app warning with reset flow, 2-minute auto-logout escalation, flashing taskbar/window
2. **Metrics Tab** — persistent session history with time-saved stats, displayed in a new tab

---

## Feature 1: Improved AFK Notification

### Current behavior

- 28-minute `threading.Timer` sends a single Discord webhook message
- No in-app feedback, no reset capability, no escalation

### New behavior

#### Timeline

| Time | Event |
|------|-------|
| 0:00 | Watch starts. AFK timer begins (28 min). Watch timer appears above Watch button as `00:00:00` (green, ticking). |
| 28:00 | **AFK Warning.** Discord ping sent. Taskbar flashes. App window flashes. In-app banner appears with "Move character to prevent AFK logout" message + **Reset AFK Timer** button. Watch timer turns orange and blinks with "PAUSED" label. Watch timer stops counting. |
| 30:00 | **Auto-logout warning** (if no reset clicked and no queue pop). Second Discord message: "Your character has most likely auto-logged out. Return to PC." AFK timer dies (no more resets possible from this cycle). Flashing and banner persist. Watch timer stays paused. Watcher keeps detecting queue pops. |

#### Resolution (one of)

- **Reset clicked** — banner dismissed, AFK timer restarts for 28 min, watch timer resumes, flashing stops
- **Queue pop detected** — everything stops, normal pop notification fires, session ends (recorded as detected=true)
- **Stop Watch clicked** — everything stops, session ends (recorded as detected=false)

#### In-app AFK banner

- Appears as a warning card overlaying the tab content area (not blocking the footer)
- Amber gradient background with left border accent
- Text: "Move character to prevent AFK logout"
- Subtext: "Then click the button below to reset the 28-minute AFK timer and continue watching."
- Full-width **Reset AFK Timer** button (amber)
- Status pill in titlebar changes to "AFK WARNING" (amber)
- Tab content is dimmed behind the banner

#### Flashing behavior

- **Taskbar flash:** Use `QApplication.alert()` or equivalent Qt method to flash the taskbar icon
- **App window flash:** CSS animation on the banner (pulsing opacity or border glow)
- Both persist until user action (reset, stop, or queue pop)

#### Discord messages

- 28-min message (existing, updated wording): `"<@{user_id}> Move character to prevent AFK logout. Watch time nearing 30 minutes."`
- 30-min message (new): `"<@{user_id}> Your character has most likely auto-logged out. Return to PC."`

### Watch timer

- **Location:** Footer area, centered above the Watch/Stop button
- **Format:** `HH:MM:SS` (always 8 characters)
- **Normal state:** Green (`#10b981`), ticking every second
- **AFK paused state:** Orange (`#f59e0b`), blinking animation, "PAUSED" label beside it
- **Hidden** when watcher is not active
- **Pauses** when AFK warning fires at 28 min
- **Resumes** when Reset AFK Timer clicked
- **Stops** when queue pop detected or watch stopped (session ends)
- Timer value represents actual active watch time (excludes paused duration)

### API changes

- New endpoint: `POST /api/reset_afk` — resets the AFK timer, dismisses banner, resumes watch timer
- New SSE events:
  - `afk_warning` — sent at 28 min, triggers in-app banner + flashing
  - `afk_logout` — sent at 30 min, triggers second Discord message
  - `afk_reset` — sent on reset, dismisses banner

### Threading model

- Existing `threading.Timer` for 28-min warning (already implemented)
- New `threading.Timer` for 2-min escalation (created when 28-min fires, cancelled if reset clicked)
- Both are daemon threads, cancelled on stop_watch or queue pop

---

## Feature 2: Metrics Tab

### Data persistence

New file: `qpopcv/metrics.json` (alongside config files, gitignored)

```json
{
  "sessions": [
    {
      "start": "2026-03-28T14:30:00",
      "end": "2026-03-28T14:42:38",
      "duration_seconds": 758,
      "detected": true
    }
  ]
}
```

- A session is recorded when the watcher stops (by any means: pop detected, manual stop, app close)
- `detected: true` means a queue pop was found; `false` means manual stop
- `duration_seconds` is active watch time only (excludes AFK-paused time)
- File loaded on app start, appended on session end, saved atomically

### Metrics displayed

All metrics show two views via an **All Time / Today** toggle:

| Metric | Calculation |
|--------|-------------|
| **Total Time Saved** | Sum of `duration_seconds` for all sessions |
| **Effective Time Saved (Queue Popped)** | Sum of `duration_seconds` where `detected=true` |
| **Pops Detected** | Count of sessions where `detected=true` |
| **Avg Queue Wait** | `Effective Time Saved / Pops Detected` |
| **Longest Session** | Max `duration_seconds` across all sessions |

- "Today" filters sessions where `start` date matches current date

### Tab layout

- **Hero card** (full width, centered): Total Time Saved — large bold number
- **Secondary card** (full width, green tint): Effective Time Saved (Queue Popped)
- **3-column row:** Pops Detected | Avg Queue Wait | Longest Session — large numbers with small labels
- Format: days/hours/minutes for large values (e.g., `2d 5h 32m`), minutes/seconds for small (e.g., `12m 38s`)

### Current session timer (live)

- Displayed in the footer above Watch/Stop button (same watch timer from Feature 1)
- Visible on ALL tabs when watcher is active, not just Metrics
- Ticks via JavaScript `setInterval` (1 second), synced with Python via SSE events for pause/resume

### API changes

- `GET /api/initial_state` response gains `metrics` field with computed stats
- `POST /api/stop_watch` response gains `session` field with the just-completed session record
- New SSE event: `metrics_update` — sent when a session completes, carries updated computed stats

### New tab registration

- Add "Metrics" as 5th tab in `index.html`
- Tab panel contains the stat cards and toggle
- CSS follows existing tab panel patterns

---

## Shared infrastructure

### Watch timer (JS-side)

- `setInterval` in `app.js` ticking once per second
- Starts on `watch_started` state, stops on `watch_stopped`
- Pauses on `afk_warning` SSE event, resumes on `afk_reset` SSE event
- Displays in footer element visible across all tabs
- Python tracks canonical elapsed time; JS timer is display-only (resyncs on SSE events)

### Session tracking (Python-side)

- `api.py` gains `_session_start_time`, `_session_paused_at`, `_session_paused_total` fields
- On watch start: record start time, reset pause accumulators
- On AFK warning: record pause start
- On AFK reset: accumulate paused duration, clear pause start
- On watch stop / pop detected: compute `duration_seconds = (now - start) - total_paused`, write session to `metrics.json`

---

## Out of scope

- AI-based queue time predictions
- Historical graphs or charts
- Export/import of metrics data
- Per-character or per-bracket tracking
