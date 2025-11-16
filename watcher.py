from pathlib import Path
from typing import Dict, Optional, Tuple, Callable, List
import threading
import time
import sys

import pyautogui
from pyautogui import ImageNotFoundException
import requests
from PIL import Image

THROTTLE_SECONDS = 15
BASELINE_UI_SCALE = 69.0

if getattr(sys, "frozen", False):
    MEDIA_ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    MEDIA_ROOT = Path(__file__).resolve().parent

MEDIA_DIR = MEDIA_ROOT / "media"

REFERENCE_IMG = [
    ("solo_shuffle_blizzui", MEDIA_DIR / "qpop_ss_blizzardUI_reference.png"),
    ("solo_shuffle_bbqui", MEDIA_DIR / "qpop_ss_bbq_reference.png"),
    ("solo_shuffle_bbqui_dark", MEDIA_DIR / "qpop_ss_bbq_dark_reference.png"),
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
        self._ui_scale = self._coerce_ui_scale(config.get("ui_scale", BASELINE_UI_SCALE))
        self._scale_factor = (
            self._ui_scale / BASELINE_UI_SCALE if BASELINE_UI_SCALE else 1.0
        )

        self._mention = f"<@{self._user_id}>"
        self._on_detect = on_detect

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_qpop_time: float = 0.0
        self._seen_once: bool = False

        self._region = self._compute_top_center_region()
        self._reference_images = self._prepare_reference_images()

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
        print(
            f"UI scale: {self._ui_scale}% "
            f"(factor {self._scale_factor:.3f} vs baseline {BASELINE_UI_SCALE}%)"
        )
        if not self._reference_images:
            print("Warning: no reference images loaded; detection will be disabled.")

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

    def _find_queue_popup(self, screenshot) -> Optional[str]:
        for name, reference in self._reference_images:
            try:
                loc = pyautogui.locate(
                    reference,
                    screenshot,
                    confidence=self._confidence,
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
        detected_at = time.time()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(detected_at))
        print(f"[{timestamp}] Queue popup detected via '{match_name}'")

        throttled, remaining, now = self._check_throttle()

        if throttled:
            print(f"Qpop throttled - skipping (wait {remaining}s).")
        else:
            try:
                send_start = time.time()
                self._send_discord_message(f"{self._mention} Your Queue has popped!")
                send_end = time.time()

                self._last_qpop_time = now
                print(f"Discord notification sent. HTTP took {send_end - send_start:.3f}s")
            except Exception as e:
                print("Error sending webhook:", e)

        # local GUI feedback timing
        gui_start = time.time()
        if self._on_detect:
            self._on_detect()
        gui_end = time.time()
        print(f"Local GUI detect effect took {gui_end - gui_start:.3f}s")

    def _loop(self) -> None:
        # Main watcher loop running in a background thread.
        while not self._stop_event.is_set():
            try:
                # Take a single screenshot of the region
                screenshot = pyautogui.screenshot(region=self._region)

                # Check all reference images against this single screenshot
                match_name = self._find_queue_popup(screenshot)
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

    @staticmethod
    def _coerce_ui_scale(value: object) -> float:
        try:
            scale = float(value)
        except (TypeError, ValueError):
            return BASELINE_UI_SCALE
        return max(65.0, min(scale, 115.0))

    def _prepare_reference_images(self) -> List[Tuple[str, Image.Image]]:
        prepared: List[Tuple[str, Image.Image]] = []
        factor = max(0.1, min(self._scale_factor, 5.0))
        for name, path in REFERENCE_IMG:
            if not path.exists():
                print(f"Missing reference image for '{name}': {path}")
                continue
            try:
                with Image.open(path) as img:
                    image = img.convert("RGB")
            except Exception as exc:
                print(f"Failed to load reference image '{name}': {exc}")
                continue
            image.load()
            if factor != 1.0:
                new_w = max(1, int(round(image.width * factor)))
                new_h = max(1, int(round(image.height * factor)))
                if (new_w, new_h) != image.size:
                    image = image.resize((new_w, new_h), Image.BICUBIC)
            prepared.append((name, image))
        return prepared
