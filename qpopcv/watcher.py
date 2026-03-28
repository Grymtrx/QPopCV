from pathlib import Path
from typing import Dict, Optional, Tuple, Callable, List
import threading
import time
from dataclasses import dataclass
import logging

import pyautogui
from pyautogui import ImageNotFoundException
import requests
from PIL import Image

from qpopcv.config import MEDIA_DIR
from qpopcv.monitor_utils import get_monitors, compute_top_center_region

THROTTLE_SECONDS = 15

logger = logging.getLogger(__name__)

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
    reference_image_paths: List[Path] = None  # type: ignore[assignment]
    monitor_index: int = 0

    def __post_init__(self):
        if self.reference_image_paths is None:
            self.reference_image_paths = []

    @classmethod
    def from_config(cls, config: Dict[str, object]) -> "WatcherSettings":
        raw_paths = config.get("reference_image_paths", [])
        if not isinstance(raw_paths, list):
            raw_paths = []
        ref_paths = [
            Path(str(p).strip()).expanduser()
            for p in raw_paths
            if str(p).strip()
        ]

        return cls(
            webhook_url=str(config.get("webhook_url", "")).strip(),
            user_id=str(config.get("user_id", "")).strip(),
            check_interval=float(config.get("check_interval", 0.5)),
            confidence=float(config.get("confidence", 0.6)),
            reference_image_paths=ref_paths,
            monitor_index=int(config.get("monitor_index", 0)),
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
        self._reference_paths = settings.reference_image_paths

        self._mention = f"<@{self._user_id}>"
        self._on_detect = on_detect

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_qpop_time: float = 0.0
        self._seen_once: bool = False

        monitors = get_monitors()
        idx = max(0, min(settings.monitor_index, len(monitors) - 1))
        monitor = monitors[idx]
        self._region = compute_top_center_region(monitor)
        self._region_source = f"Monitor {idx + 1}{' (primary)' if monitor['is_primary'] else ''}"
        self.oversized_refs: List[Path] = []
        self._reference_images = self._prepare_reference_images()


    # --------- Public API ---------

    def start(self) -> None:
        if self.is_running():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

        logger.info("QPopCV screen watcher started.")
        logger.info("Region (%s): %s", self._region_source, self._region)
        logger.info(
            "Interval: %ss, confidence: %s",
            self._check_interval,
            self._confidence,
        )
        logger.info(
            "Reference images (%d): %s",
            len(self._reference_paths),
            self._reference_paths if self._reference_paths else "none configured",
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
        logger.info("[%s] Queue popup detected via '%s'", timestamp, match_name)

        throttled, remaining, now = self._check_throttle()

        if throttled:
            logger.debug("Qpop throttled - skipping (wait %ds).", remaining)
        else:
            try:
                send_start = time.time()
                self._send_discord_message(f":queuepopblink: {self._mention} Your Queue has popped!")
                send_end = time.time()

                self._last_qpop_time = now
                logger.info("Discord notification sent. HTTP took %.3fs", send_end - send_start)
            except Exception as e:
                logger.error("Error sending webhook: %s", e)

        # local GUI feedback timing
        gui_start = time.time()
        if self._on_detect:
            self._on_detect()
        gui_end = time.time()
        logger.debug("Local GUI detect effect took %.3fs", gui_end - gui_start)

    def _loop(self) -> None:
        # Main watcher loop running in a background thread.
        while not self._stop_event.is_set():
            try:
                # Take a single screenshot of the region
                screenshot = pyautogui.screenshot(region=self._region)
                if screenshot is None:
                    logger.error("Screenshot returned None; skipping frame.")
                    continue

                # Check all reference images against this single screenshot
                match_name = self._find_queue_popup(screenshot)
                popup_active = match_name is not None

                # Transition: no popup -> popup
                if popup_active and not self._seen_once:
                    self._handle_detected_popup(match_name)
                    self._seen_once = True

                # Transition: popup -> gone
                elif not popup_active and self._seen_once:
                    logger.info("Popup gone, ready for next detection.")
                    self._seen_once = False

                if self._stop_event.wait(self._check_interval):
                    break

            except Exception as e:
                logger.error("Watcher error: %s", e)
                if self._stop_event.wait(2):
                    break

        logger.info("Watcher stopped.")

    def _prepare_reference_images(self) -> List[Tuple[str, Image.Image]]:
        prepared: List[Tuple[str, Image.Image]] = []

        for i, path in enumerate(self._reference_paths):
            if not path.exists():
                logger.warning("Reference image %d not found, skipping: %s", i, path)
                continue
            try:
                with Image.open(path) as img:
                    base = img.convert("RGB")
                    base.load()
            except Exception as exc:
                logger.error("Failed to load reference image %d (%s): %s", i, path, exc)
                continue

            # Small multi-scale around 100% for robustness
            region_w, region_h = self._region[2], self._region[3]
            added_count = 0
            for factor in (0.9, 1.0, 1.1):
                if factor == 1.0:
                    variant = base
                else:
                    new_w = max(1, int(round(base.width * factor)))
                    new_h = max(1, int(round(base.height * factor)))
                    variant = base.resize((new_w, new_h), Image.BICUBIC)
                if variant.width > region_w or variant.height > region_h:
                    logger.warning(
                        "Ref image %d scale %.1fx (%dx%d) exceeds capture region (%dx%d) — skipping variant.",
                        i, factor, variant.width, variant.height, region_w, region_h,
                    )
                    continue
                prepared.append((f"user_ref_{i}_{factor:.1f}", variant))
                added_count += 1

            if added_count == 0:
                self.oversized_refs.append(path)

            logger.info(
                "Loaded reference image %d with 3 scale variants from: %s", i, path
            )

        if not prepared:
            logger.warning("No valid reference images loaded; detection will be disabled.")

        return prepared