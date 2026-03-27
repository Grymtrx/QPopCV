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
import requests
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .config import APP_DIR, APP_VERSION, DISCORD_SERVER_URL, save_config
from .discord_client import send_test_message
from .monitor_utils import get_monitors
from .updater import UpdateInfo, UpdateManager
from .watcher import QPopWatcher, WatcherSettings

logger = logging.getLogger(__name__)

TEST_THROTTLE_SECONDS = 1


# ── Pure validation ────────────────────────────────────────────────────────────

def _validate_discord(webhook_url: str, user_id: str) -> Optional[str]:
    """Return an error string, or None if valid."""
    webhook_url = webhook_url.strip()
    user_id = user_id.strip()
    if not webhook_url:
        return "Please set the Discord Webhook URL."
    if not webhook_url.startswith("https://discord.com/api/webhooks/"):
        return "Webhook URL must start with https://discord.com/api/webhooks/"
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
                "webhook_url": str(self.config.get("webhook_url", "")),
                "user_id": str(self.config.get("user_id", "")),
                "reference_image_paths": [str(p) for p in self.config.get("reference_image_paths", [])],
                "monitor_index": saved_idx,
                "afk_notify": bool(self.config.get("afk_notify", False)),
            },
            "monitors": labels,
        }

    # ── Watch control ──────────────────────────────────────────────────────────

    def start_watch(self, data: dict) -> dict:
        webhook_url = str(data.get("webhook_url", "")).strip()
        user_id = str(data.get("user_id", "")).strip()
        paths = [str(p) for p in data.get("reference_image_paths", [])]
        monitor_index = int(data.get("monitor_index", 0))
        afk_notify = bool(data.get("afk_notify", False))
        skip_discord_check = bool(data.get("skip_discord_check", False))

        err = _validate_discord(webhook_url, user_id)
        if err:
            return {"ok": False, "error": err}
        err = _validate_ref_images(paths)
        if err:
            return {"ok": False, "error": err}

        if not skip_discord_check and _is_discord_running():
            return {"ok": False, "discord_running": True}

        self.config["webhook_url"] = webhook_url
        self.config["user_id"] = user_id
        self.config["reference_image_paths"] = [p for p in paths if p.strip()]
        self.config["monitor_index"] = monitor_index
        self.config["afk_notify"] = afk_notify
        save_config(self.config)

        settings = WatcherSettings.from_config(self.config)
        self._watcher = QPopWatcher(settings, on_detect=self._on_detection)
        self._watcher.start()

        if self._afk_timer:
            self._afk_timer.cancel()
            self._afk_timer = None

        if afk_notify:
            self._afk_timer = threading.Timer(28 * 60, self._send_afk_notification)
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

    def stop_watch(self) -> dict:
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
        if self._afk_timer:
            self._afk_timer.cancel()
            self._afk_timer = None
        return {"ok": True}

    def kill_discord(self) -> dict:
        """Terminate all running Discord.exe processes."""
        try:
            for proc in psutil.process_iter(["name"]):
                try:
                    if proc.name().lower() == "discord.exe":
                        proc.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as exc:
            logger.error("kill_discord failed: %s", exc)
            return {"ok": False, "error": str(exc)}
        return {"ok": True}

    def save_config_data(self, data: dict) -> dict:
        """Save settings without starting the watcher."""
        self.config["webhook_url"] = str(data.get("webhook_url", "")).strip()
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

        webhook_url = str(data.get("webhook_url", "")).strip()
        user_id = str(data.get("user_id", "")).strip()

        err = _validate_discord(webhook_url, user_id)
        if err:
            return {"ok": False, "error": err}

        try:
            send_test_message(webhook_url, user_id, timeout=5.0)
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
        self._push("detected", None)

    def _send_afk_notification(self) -> None:
        """Called by threading.Timer after 28 minutes of watching."""
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
        self._afk_timer = None  # CPython GIL makes this write atomic; double-None with stop_watch is benign.

    def _cleanup(self) -> None:
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
        if self._afk_timer:
            self._afk_timer.cancel()
            self._afk_timer = None
