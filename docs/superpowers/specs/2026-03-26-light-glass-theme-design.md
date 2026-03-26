# Light Glassmorphic Theme — Pearl White

**Date:** 2026-03-26
**Status:** Approved

## Context

Replace the current Discord dark palette with a light glassmorphic "Pearl White" theme. The app should feel crisp, clean, and organized — white glass panels over a soft light-gray background, with Discord blurple as the primary accent.

## Color Palette

| CSS Variable | Value | Purpose |
|---|---|---|
| `--glass-bg` | `#f4f6f9` | Main app background |
| `--glass-surface` | `rgba(255,255,255,0.70)` | Titlebar, footer |
| `--glass-raised` | `rgba(255,255,255,0.50)` | Input backgrounds |
| `--border` | `rgba(0,0,0,0.09)` | Standard borders |
| `--border-bright` | `rgba(0,0,0,0.16)` | Hover/focus borders |
| `--border-subtle` | `rgba(0,0,0,0.05)` | Dividers |
| `--text` | `#111827` | Primary text |
| `--text-secondary` | `#374151` | Secondary text |
| `--text-muted` | `#6b7280` | Labels, hints |
| `--text-dim` | `#9ca3af` | Placeholders, dots |
| `--green` | `#16a34a` | Watch active / success |
| `--green-glow` | `rgba(22,163,74,0.18)` | Green pulse |
| `--orange` | `#d97706` | Detected state |
| `--orange-glow` | `rgba(217,119,6,0.25)` | Orange pulse |
| `--red` | `#dc2626` | Errors, close hover |
| `--blue` | `#2563eb` | Info toasts |
| `--discord` | `#5865f2` | Unchanged |
| `--discord-hover` | `#4752c4` | Unchanged |

## Component Changes

### App card
- Re-enable `backdrop-filter: blur(20px) saturate(160%)` for true glass feel
- Box shadow: soft light-bg shadow — `0 8px 32px rgba(0,0,0,0.10), 0 2px 8px rgba(0,0,0,0.06)`
- Top seam refraction: use dark gradient `rgba(0,0,0,0.06)` instead of white

### Titlebar & footer
- Background: `var(--glass-surface)` (white glass layer)
- Logo dot: blurple `#5865f2`

### Tabs
- Active underline: `#5865f2` instead of white
- Hover background: `rgba(0,0,0,0.03)`

### Inputs & selects
- Background: `var(--glass-raised)`
- Focus ring: `rgba(88,101,242,0.18)` blurple
- Dropdown arrow SVG: dark stroke `rgba(0,0,0,0.4)`
- Select option bg: `#f4f6f9`

### Watch button
- Idle: solid `#5865f2` with white text (primary CTA on light bg)
- Hover: `#4752c4`
- Watching: green `rgba(22,163,74,0.12)` tint with green border/text

### Window buttons
- Min hover: dark tint
- Close hover: red tint (same approach, adjusted for light bg)

### Toasts
- Background: `rgba(255,255,255,0.95)` with dark text
- Border: light with colored accent per type

### Status pill states
- Watching: `rgba(22,163,74,0.08)` bg, `rgba(22,163,74,0.25)` border
- Detected: `rgba(217,119,6,0.10)` bg, `rgba(217,119,6,0.40)` border

### Save button
- Background: `rgba(0,0,0,0.04)`, border: `rgba(0,0,0,0.09)`, text: `--text-secondary`

## Files to Modify

- `qpopcv/static/style.css` — full palette swap + component adjustments
- `qpopcv/app_ui.py` — web view bg color → `QColor(244, 246, 249)`
- `qpopcv/config.py` — version bump to `1.0.36`
