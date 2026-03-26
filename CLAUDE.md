# QPopCV

WoW Solo Shuffle queue-pop detector. Windows-only Python app — CustomTkinter GUI + template matching → Discord webhook ping.

## Docs
- Architecture & threading model: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Per-file module reference: [docs/CODEBASE.md](docs/CODEBASE.md)
- Known issues & roadmap: [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md)

## Key facts
- Entry point: `main.py` → `qpopcv/app_ui.py` (`QPopApp`)
- Detection engine: `qpopcv/watcher.py` (daemon thread)
- Config: `qpopcv/config.json` (loaded via `qpopcv/config.py`)
- Python 3.11+, Windows only

## Versioning
Increment the patch version (`APP_VERSION` in `qpopcv/config.py`) on every code change. Current version: `1.0.6`.

## Active work order (see KNOWN_ISSUES.md for full list)
SEC-01 is deferred. BUG-02 fixed (v1.0.5), AP-01 fixed (v1.0.6). Start from GAP-07.
