from pathlib import Path
from typing import Dict, Optional, Tuple, Callable
import threading
import time

import pyautogui
from pyautogui import ImageNotFoundException
import requests

THROTTLE_SECONDS = 15

REFERENCE_IMG = [
    ("solo_shuffle_blizzui", Path("media/qpop_ss_blizzardUI_reference.png")),
    ("solo_shuffle_bbqui", Path("media/qpop_ss_bbq_reference.png")),
    ("solo_shuffle_bbqui_dark", Path("media/qpop_ss_bbq_dark_reference.png")),
]


class QPopWatcher:
    """
    Screen-based queue popup watcher.
    - Scans the top-center of the screen for reference images.
    - Sends a Discord webhook when a popup is detected (throttled).
    - Calls an optional callback when a popup is detected (for GUI effects).
    """

    def __init__(
        self,
        config: Dict[str, object],
        on_detect: Optional[Callable[[], None]] = None,
    ) -> None:
        self._webhook_url = str(config.get("webhook_url", "")).strip()
        self._user_id = str(config.get("user_id", "")).strip()
        self._check_interval = float(config.get("check_interval", 0.5))
        self._confidence = float(config.get("confidence", 0.6))

        self._mention = f"<@{self._user_id}>"
        self._on_detect = on_detect

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_qpop_time: float = 0.0
        self._seen_once: bool = False

        self._region = self._compute_top_center_region()

    # --------- Public API ---------

    def start(self) -> None:
        if self.is_running():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

        print("QPopCV screen watcher started.")
        print(f"Region (top-center): {self._region}")
        print(f"Interval: {self._check_interval}s, confidence: {self._confidence}")

        for name, path in REFERENCE_IMG:
            if not path.exists():
                print(f"Missing reference image for '{name}': {path}")

    def stop(self) -> None:
        self._stop_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # --------- Internal Helpers ---------

    @staticmethod
    def _compute_top_center_region() -> Tuple[int, int, int, int]:
        screen_w, screen_h = pyautogui.size()
        region_x = screen_w // 3
        region_y = 0
        region_w = screen_w // 3
        region_h = screen_h // 2
        return region_x, region_y, region_w, region_h

    def _find_queue_popup(self) -> Optional[str]:
        for name, path in REFERENCE_IMG:
            if not path.exists():
                continue
            try:
                loc = pyautogui.locateOnScreen(
                    str(path),
                    confidence=self._confidence,
                    region=self._region,
                )
            except ImageNotFoundException:
                loc = None

            if loc is not None:
                return name

        return None

    def _send_discord_message(self, content: str) -> None:
        requests.post(
            self._webhook_url,
            json={"content": content},
            timeout=5,
        )

    def _check_throttle(self) -> Tuple[bool, int, float]:
        now = time.time()
        elapsed = now - self._last_qpop_time
        if elapsed < THROTTLE_SECONDS:
            remaining = int(THROTTLE_SECONDS - elapsed)
            return True, remaining, now
        return False, 0, now

    def _handle_detected_popup(self, match_name: str) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] Queue popup detected via '{match_name}'")

        throttled, remaining, now = self._check_throttle()

        if throttled:
            print(f"⏳ Qpop! throttled — skipping (wait {remaining}s).")
        else:
            try:
                self._send_discord_message(f"{self._mention} Your Queue has popped!")
                self._last_qpop_time = now
                print("Discord notification sent.")
            except Exception as e:
                print("Error sending webhook:", e)

        if self._on_detect:
            self._on_detect()

    def _loop(self) -> None:
        """Main watcher loop running in a background thread."""
        while not self._stop_event.is_set():
            try:
                match_name = self._find_queue_popup()
                popup_active = match_name is not None

                # Transition: no popup -> popup
                if popup_active and not self._seen_once:
                    self._handle_detected_popup(match_name)
                    self._seen_once = True

                # Transition: popup -> gone
                elif not popup_active and self._seen_once:
                    print("Popup gone, ready for next detection.")
                    self._seen_once = False

                if self._stop_event.wait(self._check_interval):
                    break

            except Exception as e:
                print("Watcher error:", e)
                if self._stop_event.wait(2):
                    break

        print("Watcher stopped.")