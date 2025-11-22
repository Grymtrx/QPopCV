from pathlib import Path
from typing import Dict, Optional, Tuple, Callable, List
import threading
import time
import sys
from dataclasses import dataclass
import logging

import pyautogui
from pyautogui import ImageNotFoundException
import requests
from PIL import Image

THROTTLE_SECONDS = 15

logger = logging.getLogger(__name__)

if getattr(sys, "frozen", False):
    MEDIA_ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    MEDIA_ROOT = Path(__file__).resolve().parent

MEDIA_DIR = MEDIA_ROOT / "media"

# Built-in fallback references (for your own setup)
REFERENCE_IMG = [
    ("solo_shuffle_blizzui", MEDIA_DIR / "qpop_ss_blizzardUI_reference.png"),
    ("solo_shuffle_bbqui", MEDIA_DIR / "qpop_ss_bbq_reference.png"),
    ("solo_shuffle_bbqui_dark", MEDIA_DIR / "qpop_ss_bbq_dark_reference.png"),
]

@dataclass
class WatcherSettings:
    webhook_url: str
    user_id: str
    check_interval: float = 0.5
    confidence: float = 0.6
    reference_image_path: Optional[Path] = None

    @classmethod
    def from_config(cls, config: Dict[str, object]) -> "WatcherSettings":
        ref_path_str = str(config.get("reference_image_path", "")).strip()
        ref_path = Path(ref_path_str).expanduser() if ref_path_str else None

        return cls(
            webhook_url=str(config.get("webhook_url", "")).strip(),
            user_id=str(config.get("user_id", "")).strip(),
            check_interval=float(config.get("check_interval", 0.5)),
            confidence=float(config.get("confidence", 0.6)),
            reference_image_path=ref_path,
        )



class QPopWatcher:
    """
    Screen-based queue popup watcher.
    - Scans the top-center of the screen for reference images.
    - Sends a Discord webhook when a popup is detected (throttled).
    - Calls an optional callback when a popup is detected (for GUI effects).

    Now supports per-user calibration via `reference_image_path` in config:
    - If provided and valid, uses that as the primary reference (with small
      multi-scale variants around 100%).
    - If not provided, falls back to built-in reference images.
    """

    def __init__(
        self,
        settings: WatcherSettings,
        on_detect: Optional[Callable[[], None]] = None,
    ) -> None:
        self._webhook_url = settings.webhook_url.strip()
        self._user_id = settings.user_id.strip()
        self._check_interval = float(settings.check_interval)
        self._confidence = float(settings.confidence)
        self._reference_path = settings.reference_image_path

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

        logger.info("QPopCV screen watcher started.")
        logger.info("Region (top-center): %s", self._region)
        logger.info(
            "Interval: %ss, confidence: %s",
            self._check_interval,
            self._confidence,
        )
        logger.info(
            "Reference image: %s",
            self._reference_path if self._reference_path else "built-in defaults",
        )
        if not self._reference_images:
            logger.warning(
                "No reference images prepared. Detection will not work correctly."
            )


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

    def _prepare_reference_images(self) -> List[Tuple[str, Image.Image]]:
        prepared: List[Tuple[str, Image.Image]] = []

        # Only use user-provided reference image
        if self._reference_path and self._reference_path.exists():
            try:
                with Image.open(self._reference_path) as img:
                    base = img.convert("RGB")
                    base.load()
            except Exception as exc:
                print(f"Failed to load user reference image: {exc}")
                return prepared

            # Small multi-scale around 100% for robustness
            for factor in (0.9, 1.0, 1.1):
                if factor == 1.0:
                    variant = base
                else:
                    new_w = max(1, int(round(base.width * factor)))
                    new_h = max(1, int(round(base.height * factor)))
                    variant = base.resize((new_w, new_h), Image.BICUBIC)
                prepared.append((f"user_ref_{factor:.1f}", variant))

            print(
                f"Loaded ONLY user reference image with {len(prepared)} scale variants "
                f"from: {self._reference_path}"
            )
            return prepared

        # No fallback at all while testing
        print("No valid user reference image; detection will be disabled (no fallbacks).")
        return prepared