"""
QPopCV API logic layer.

Framework-agnostic — no pywebview, no Qt, no tkinter imports.
Called by app_ui.py's embedded HTTP server.
"""
from __future__ import annotations

import logging
import threading
import time
import webbrowser
import psutil
from pathlib import Path
from typing import Callable, Dict, List, Optional
from datetime import datetime, date
from .messages import AFK_WARN_DELAY, AFK_LOGOUT_DELAY
from .metrics import MetricsStore

from .config import APP_DIR, APP_VERSION, DISCORD_SERVER_URL, save_config
from .discord_client import notify, send_test_message
from .monitor_utils import get_monitors
from .updater import UpdateInfo, UpdateManager
from .watcher import QPopWatcher, WatcherSettings

logger = logging.getLogger(__name__)

TEST_THROTTLE_SECONDS = 1


# ── Pure validation ────────────────────────────────────────────────────────────

def _validate_discord(user_id: str) -> Optional[str]:
    """Return an error string, or None if valid."""
    user_id = user_id.strip()
    if not user_id:
        return "Please set your Discord User ID."
    if not (user_id.isdigit() and 17 <= len(user_id) <= 19):
        return "Enter your Discord User ID — a 17–19 digit number (not your username)."
    return None


def _validate_ref_images(paths: List[str]) -> Optional[str]:
    """Return an error string, or None if valid."""
    non_empty = [p.strip() for p in paths if p.strip()]
    if not non_empty:
        return "Please select at least one reference image file."
    for path_str in non_empty:
        p = Path(path_str).expanduser()
        if not p.exists() or p.is_dir():
            return f"Reference image not found:\n{path_str}"
    return None


def _is_discord_running() -> bool:
    """Return True if any Discord.exe process is currently running."""
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.name().lower() == "discord.exe":
                return True
        except psutil.NoSuchProcess:
            pass
    return False


# ── API class ──────────────────────────────────────────────────────────────────

class Api:
    """
    All application logic, exposed to the JS frontend via the HTTP server.

    `push_event(event_type, data)` is a callback that sends an SSE event to JS.
    `quit_fn()` is called when the app should exit (e.g. after update install).
    """

    def __init__(
        self,
        config: Dict,
        push_event: Callable[[str, Optional[dict]], None],
        quit_fn: Optional[Callable] = None,
    ) -> None:
        self.config = config
        self._push = push_event
        self._quit_fn = quit_fn
        self._watcher: Optional[QPopWatcher] = None
        self._update_info: Optional[UpdateInfo] = None
        self._last_test_time: float = 0.0
        self._afk_timer: Optional[threading.Timer] = None
        self._afk_escalation_timer: Optional[threading.Timer] = None
        self._afk_warned: bool = False
        self._session_lock = threading.Lock()
        self._session_start_time: Optional[datetime] = None
        self._session_start_mono: Optional[float] = None
        self._session_paused_at: Optional[float] = None
        self._session_paused_total: float = 0.0
        self._metrics = MetricsStore(APP_DIR / "metrics.json")
        self.update_manager = UpdateManager(current_version=APP_VERSION, app_dir=APP_DIR)

    # ── Initial state ──────────────────────────────────────────────────────────

    def get_initial_state(self) -> dict:
        monitors = get_monitors()
        labels: List[str] = []
        for i, m in enumerate(monitors):
            label = f"Monitor {i + 1}"
            if m["is_primary"]:
                label += " \u2013 Primary"
            labels.append(label)

        saved_idx = int(str(self.config.get("monitor_index", 0)))
        saved_idx = max(0, min(saved_idx, len(labels) - 1))

        return {
            "version": APP_VERSION,
            "config": {
                "user_id": str(self.config.get("user_id", "")),
                "reference_image_paths": [str(p) for p in self.config.get("reference_image_paths", [])],
                "monitor_index": saved_idx,
                "afk_notify": bool(self.config.get("afk_notify", False)),
            },
            "monitors": labels,
            "metrics": {
                "all_time": self._metrics.compute(),
                "today": self._metrics.compute(day=date.today()),
            },
        }

    # ── Watch control ──────────────────────────────────────────────────────────

    def start_watch(self, data: dict) -> dict:
        user_id = str(data.get("user_id", "")).strip()
        paths = [str(p) for p in data.get("reference_image_paths", [])]
        monitor_index = int(data.get("monitor_index", 0))
        afk_notify = bool(data.get("afk_notify", False))
        skip_discord_check = bool(data.get("skip_discord_check", False))

        err = _validate_discord(user_id)
        if err:
            return {"ok": False, "error": err}
        err = _validate_ref_images(paths)
        if err:
            return {"ok": False, "error": err}

        if not skip_discord_check and _is_discord_running():
            return {"ok": False, "discord_running": True}

        self.config["user_id"] = user_id
        self.config["reference_image_paths"] = [p for p in paths if p.strip()]
        self.config["monitor_index"] = monitor_index
        self.config["afk_notify"] = afk_notify
        save_config(self.config)

        # Stop any existing watcher before creating a new one
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None

        settings = WatcherSettings.from_config(self.config)
        self._watcher = QPopWatcher(settings, on_detect=self._on_detection)
        self._watcher.start()

        with self._session_lock:
            self._session_start_time = datetime.now()
            self._session_start_mono = time.monotonic()
            self._session_paused_at = None
            self._session_paused_total = 0.0
        self._afk_warned = False

        if self._afk_timer:
            self._afk_timer.cancel()
            self._afk_timer = None
        if self._afk_escalation_timer:
            self._afk_escalation_timer.cancel()
            self._afk_escalation_timer = None

        if afk_notify:
            self._afk_timer = threading.Timer(AFK_WARN_DELAY, self._send_afk_warning)
            self._afk_timer.daemon = True
            self._afk_timer.start()

        warning = None
        if self._watcher.oversized_refs:
            names = ", ".join(p.name for p in self._watcher.oversized_refs)
            rw, rh = self._watcher._region[2], self._watcher._region[3]
            warning = (
                f"Image(s) larger than the detection zone ({rw}\u00d7{rh}px) will be ignored: "
                f"{names}. Use a cropped screenshot of just the queue popup."
            )

        return {"ok": True, "warning": warning}

    def stop_watch(self, detected: bool = False) -> dict:
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
        if self._afk_timer:
            self._afk_timer.cancel()
            self._afk_timer = None
        if self._afk_escalation_timer:
            self._afk_escalation_timer.cancel()
            self._afk_escalation_timer = None
        self._afk_warned = False

        session = self._end_session(detected)
        return {"ok": True, "session": session}

    def kill_discord(self) -> dict:
        """Terminate all running Discord.exe processes and wait for them to exit."""
        procs = []
        try:
            for proc in psutil.process_iter(["name"]):
                try:
                    if proc.name().lower() == "discord.exe":
                        proc.terminate()
                        procs.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as exc:
            logger.error("kill_discord failed: %s", exc)
            return {"ok": False, "error": str(exc)}

        # Wait for processes to actually exit
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                pass

        # Give Discord's Gateway time to detect the dropped connection
        # and reroute subsequent notifications to mobile
        time.sleep(3)
        return {"ok": True}

    def save_config_data(self, data: dict) -> dict:
        """Save settings without starting the watcher."""
        self.config["user_id"] = str(data.get("user_id", "")).strip()
        paths = [str(p) for p in data.get("reference_image_paths", [])]
        self.config["reference_image_paths"] = [p for p in paths if p.strip()]
        self.config["monitor_index"] = int(data.get("monitor_index", 0))
        self.config["afk_notify"] = bool(data.get("afk_notify", False))
        save_config(self.config)
        return {"ok": True}

    # ── Discord ────────────────────────────────────────────────────────────────

    def test_discord(self, data: dict) -> dict:
        now = time.time()
        if now - self._last_test_time < TEST_THROTTLE_SECONDS:
            remaining = int(TEST_THROTTLE_SECONDS - (now - self._last_test_time))
            return {"ok": False, "error": f"Wait {remaining}s before testing again."}

        user_id = str(data.get("user_id", "")).strip()

        err = _validate_discord(user_id)
        if err:
            return {"ok": False, "error": err}

        try:
            send_test_message(user_id, timeout=5.0)
            self._last_test_time = now
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def open_discord(self) -> None:
        webbrowser.open(DISCORD_SERVER_URL)

    # ── Updater ────────────────────────────────────────────────────────────────

    def check_for_updates(self) -> None:
        def worker() -> None:
            try:
                info = self.update_manager.check_for_update()
                self._update_info = info
                if info.available and info.download_url:
                    self._push("update_status", {"available": True, "version": info.latest_version})
                else:
                    self._push("update_status", {"available": False})
            except Exception as exc:
                logger.exception("Update check failed: %s", exc)
                self._push("update_status", {"available": False})

        threading.Thread(target=worker, daemon=True).start()

    def install_update(self) -> dict:
        if not self._update_info or not self._update_info.available:
            return {"ok": False, "error": "No update available."}

        def worker() -> None:
            try:
                self.update_manager.install_update(self._update_info)
                self._push("update_progress", {"state": "installed"})
                time.sleep(1.5)
                if self._quit_fn:
                    self._quit_fn()
            except Exception as exc:
                logger.exception("Update install failed: %s", exc)
                self._push("update_progress", {"state": "failed", "error": str(exc)[:100]})

        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True}

    # ── Internal callbacks ─────────────────────────────────────────────────────

    def _on_detection(self) -> None:
        """Called from QPopWatcher daemon thread on queue-pop detection."""
        self.stop_watch(detected=True)
        self._push("detected", None)

    def _send_afk_warning(self) -> None:
        """Called by threading.Timer after 28 minutes of watching."""
        self._afk_warned = True
        with self._session_lock:
            self._session_paused_at = time.monotonic()

        user_id = str(self.config.get("user_id", "")).strip()
        if user_id:
            notify(user_id, "afk_warn")

        self._push("afk_warning", None)

        self._afk_escalation_timer = threading.Timer(AFK_LOGOUT_DELAY, self._send_afk_logout)
        self._afk_escalation_timer.daemon = True
        self._afk_escalation_timer.start()

    def _send_afk_logout(self) -> None:
        """Called 2 minutes after AFK warning if user hasn't reset."""
        user_id = str(self.config.get("user_id", "")).strip()
        if user_id:
            notify(user_id, "afk_logout")

        self._afk_escalation_timer = None
        self._push("afk_logout", None)

    def reset_afk(self) -> dict:
        """Reset the AFK timer — called when user clicks Reset AFK Timer button."""
        if not self._afk_warned:
            return {"ok": False, "error": "No AFK warning active."}

        if self._afk_escalation_timer:
            self._afk_escalation_timer.cancel()
            self._afk_escalation_timer = None

        # Resume session timer
        with self._session_lock:
            if self._session_paused_at is not None:
                self._session_paused_total += time.monotonic() - self._session_paused_at
                self._session_paused_at = None

        self._afk_warned = False

        # Restart 28-min AFK timer
        if self._afk_timer:
            self._afk_timer.cancel()
        self._afk_timer = threading.Timer(AFK_WARN_DELAY, self._send_afk_warning)
        self._afk_timer.daemon = True
        self._afk_timer.start()

        self._push("afk_reset", None)
        return {"ok": True}

    def _end_session(self, detected: bool) -> Optional[dict]:
        """Record session to metrics store. Returns session dict or None."""
        with self._session_lock:
            if self._session_start_time is None:
                return None

            now = datetime.now()
            elapsed_mono = time.monotonic() - self._session_start_mono

            # If currently paused, add the current pause duration
            if self._session_paused_at is not None:
                self._session_paused_total += time.monotonic() - self._session_paused_at
                self._session_paused_at = None

            duration = max(0, int(elapsed_mono - self._session_paused_total))

            start_time = self._session_start_time
            self._session_start_time = None
            self._session_start_mono = None
            self._session_paused_total = 0.0

        session = self._metrics.record_session(
            start=start_time,
            end=now,
            duration_seconds=duration,
            detected=detected,
        )

        # Push updated metrics to JS
        self._push("metrics_update", {
            "all_time": self._metrics.compute(),
            "today": self._metrics.compute(day=date.today()),
        })

        return session

    def _cleanup(self) -> None:
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
        if self._afk_timer:
            self._afk_timer.cancel()
            self._afk_timer = None
        if self._afk_escalation_timer:
            self._afk_escalation_timer.cancel()
            self._afk_escalation_timer = None
