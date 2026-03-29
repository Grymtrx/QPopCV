# UI Polish — Persistent Detection, Eye Toggle, Always-on-Top

**Date:** 2026-03-28

## Features

### 1. Persistent "Detected!" State

**What:** When a queue pop is detected, the yellow status pill ("Detected!") stays visible until the user explicitly clicks Watch again. Currently it auto-resets to idle after 1.6s.

**Change:** Remove the `setTimeout` in `onDetected()` (app.js) that calls `setStatus('idle')` after 1600ms. The detected state clears naturally when the user starts watching (`setStatus('watching')`) or stops (`setStatus('idle')`).

**No other changes needed.**

---

### 2. Eye Icon on User ID Field

**What:** The User ID input (`type="password"`) gets a small eye button on its right edge. Clicking it reveals the value as plain text for 5 seconds, then auto-hides. Clicking again while visible resets the 5s timer.

**Implementation (index.html + style.css + app.js):**
- Wrap the `#user-id` input in a `<div class="field-input-wrap">` with `position: relative`
- Add `<button class="eye-btn" id="eye-btn" type="button">` absolutely positioned inside the wrapper
- Eye icon: SVG eye (open/closed states) or Unicode `◎`/`●`
- On click: `input.type = 'text'`, clear any existing timer, start `setTimeout(hide, 5000)`
- On timeout: `input.type = 'password'`
- Eye button styled to match existing muted icon buttons; no border, transparent background

---

### 3. Always on Top + 50% Opacity When Unfocused

**What:** The app window floats above all other windows at all times. When it loses focus it becomes 50% transparent; regains full opacity when focused.

**Implementation (app_ui.py only):**
- Add `Qt.WindowType.WindowStaysOnTopHint` to `setWindowFlags(...)` in `run()`
- Subclass `QMainWindow` (or install an event filter) to override `changeEvent`:
  - On `QEvent.Type.ActivationChange`: call `self.setWindowOpacity(1.0 if self.isActiveWindow() else 0.5)`

**No JS/SSE changes needed.**

---

## Files Changed

| File | Change |
|------|--------|
| `qpopcv/static/app.js` | Remove `setTimeout` reset in `onDetected()` |
| `qpopcv/static/index.html` | Wrap user-id input, add eye button |
| `qpopcv/static/style.css` | Style `.field-input-wrap` and `.eye-btn` |
| `qpopcv/static/app.js` | Eye button click handler + 5s timer |
| `qpopcv/app_ui.py` | Always-on-top flag + opacity on activation change |
