# QPopCV

WoW Solo Shuffle queue-pop detector. Windows-only Python app — pywebview GUI (HTML/CSS/JS frontend) + template matching → Discord webhook ping.

## Docs
- Architecture & threading model: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Per-file module reference: [docs/CODEBASE.md](docs/CODEBASE.md)
- Known issues & roadmap: [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md)

## Key facts
- Entry point: `main.py` → `qpopcv/app_ui.py` (`QPopApp`)
- UI: PyQt6 + QWebEngineView loading `http://127.0.0.1:PORT/` (local HTTP server)
- Frontend: `qpopcv/static/` — `index.html`, `style.css`, `app.js`
- API bridge: `qpopcv/api.py` (pure logic) + HTTP routes in `app_ui.py`
- JS → Python: `fetch('/api/...')` POST calls returning JSON
- Python → JS: Server-Sent Events (`EventSource('/events')`)
- Detection engine: `qpopcv/watcher.py` (daemon thread)
- Config: `qpopcv/config.json` (shared defaults) + `qpopcv/config.local.json` (user settings, gitignored), both loaded via `qpopcv/config.py`
- Python 3.11+, Windows only (tested on 3.14)

## Versioning
Increment the patch version (`APP_VERSION` in `qpopcv/config.py`) on every code change. Current version: `1.2.0`.

## Active work order (see KNOWN_ISSUES.md for full list)
SEC-01 is deferred. BUG-02 fixed (v1.0.5), AP-01 fixed (v1.0.6), GAP-07/SEC-02/GAP-01 fixed (v1.0.7), SEC-03/SEC-05/BUG-01/BUG-03 fixed (v1.0.8), SEC-06/AP-02 fixed (v1.0.9), GAP-02/GAP-04 fixed (v1.0.10), GAP-03 fixed (v1.0.12). UI/UX audit pass done (v1.0.15). Full UI redesign (v1.0.16). UI/UX layout restructure + test fixes (v1.0.22). Full UI redesign with tabs (v1.0.23). Migrated UI from CustomTkinter to pywebview + HTML/CSS/JS (v1.0.24). Save button promoted to full-width footer row (v1.0.32). Theme switched to Pearl White light glassmorphic (v1.0.36). AFK tab added with 28-min Discord notification (v1.0.38). AP-03/04/06 retroactively closed (removed by v1.0.24 migration). AP-05/SEC-04 fixed + SHA-256 zip verification added (v1.0.39). Discord process detection added — warns user if Discord is running on Watch click, with Kill Discord / Continue Anyway options (v1.0.40). Fixed banner not dismissing after Kill Discord (v1.0.41). All known issues resolved except SEC-01 (deferred). No open items. v1.1.0 release — first official release with full update flow testing. Fix window not resizing after Discord banner dismissed (v1.1.1). v1.2.0 — AFK notification improvement (in-app warning banner, 2-min escalation to auto-logout Discord msg, Reset AFK Timer button, watch timer HH:MM:SS with pause/resume) + Metrics tab (persistent session tracking, Total/Effective time saved, pops detected, avg queue wait, longest session, All Time/Today toggle).
