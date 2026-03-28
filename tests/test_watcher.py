"""
Tests for qpopcv/watcher.py

pyautogui and requests are mocked throughout — no screen access, no network calls.
PIL image operations use real tiny in-memory images to keep tests fast.
"""
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from PIL import Image

from qpopcv.watcher import WatcherSettings, QPopWatcher, THROTTLE_SECONDS
from qpopcv.monitor_utils import compute_top_center_region
from qpopcv.messages import QUEUE_POP


# ===========================================================================
# Helpers
# ===========================================================================

VALID_WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/token"
VALID_USER_ID = "123456789012345678"


def make_settings(**overrides) -> WatcherSettings:
    base = dict(
        webhook_url=VALID_WEBHOOK,
        user_id=VALID_USER_ID,
        check_interval=0.05,
        confidence=0.6,
        reference_image_paths=[],
    )
    base.update(overrides)
    return WatcherSettings(**base)


def make_tiny_png(tmp_path: Path, name="ref.png") -> Path:
    """Write a tiny 10x10 white PNG to tmp_path and return its path."""
    p = tmp_path / name
    img = Image.new("RGB", (10, 10), color=(255, 255, 255))
    img.save(str(p))
    return p


MOCK_MONITORS = [{"x": 0, "y": 0, "w": 1920, "h": 1080, "is_primary": True}]


# ===========================================================================
# WatcherSettings.from_config
# ===========================================================================

class TestWatcherSettingsFromConfig:

    def test_basic_values_parsed(self):
        config = {
            "webhook_url": VALID_WEBHOOK,
            "user_id": VALID_USER_ID,
            "check_interval": 0.25,
            "confidence": 0.75,
            "reference_image_paths": [],
        }
        s = WatcherSettings.from_config(config)
        assert s.webhook_url == VALID_WEBHOOK
        assert s.user_id == VALID_USER_ID
        assert s.check_interval == 0.25
        assert s.confidence == 0.75
        assert s.reference_image_paths == []

    def test_empty_reference_image_paths_becomes_empty_list(self):
        config = {"webhook_url": VALID_WEBHOOK, "user_id": VALID_USER_ID,
                  "reference_image_paths": []}
        s = WatcherSettings.from_config(config)
        assert s.reference_image_paths == []

    def test_blank_string_entries_are_filtered_out(self):
        config = {"webhook_url": VALID_WEBHOOK, "user_id": VALID_USER_ID,
                  "reference_image_paths": ["", "   "]}
        s = WatcherSettings.from_config(config)
        assert s.reference_image_paths == []

    def test_valid_reference_image_paths_are_set(self, tmp_path):
        img = tmp_path / "ref.png"
        img.write_bytes(b"fake")
        config = {"webhook_url": VALID_WEBHOOK, "user_id": VALID_USER_ID,
                  "reference_image_paths": [str(img)]}
        s = WatcherSettings.from_config(config)
        assert s.reference_image_paths == [Path(str(img)).expanduser()]

    def test_webhook_url_is_stripped(self):
        config = {"webhook_url": f"  {VALID_WEBHOOK}  ", "user_id": VALID_USER_ID,
                  "reference_image_paths": []}
        s = WatcherSettings.from_config(config)
        assert s.webhook_url == VALID_WEBHOOK

    def test_missing_keys_use_defaults(self):
        config = {"webhook_url": VALID_WEBHOOK, "user_id": VALID_USER_ID}
        s = WatcherSettings.from_config(config)
        assert s.check_interval == 0.5
        assert s.confidence == 0.6


# ===========================================================================
# monitor_utils.compute_top_center_region
# ===========================================================================

class TestComputeTopCenterRegion:

    def test_region_for_1920x1080(self):
        monitor = {"x": 0, "y": 0, "w": 1920, "h": 1080, "is_primary": True}
        x, y, w, h = compute_top_center_region(monitor)
        assert x == 640   # 0 + 1920 // 3
        assert y == 0
        assert w == 640   # 1920 // 3
        assert h == 540   # 1080 // 2

    def test_region_for_2560x1440(self):
        monitor = {"x": 0, "y": 0, "w": 2560, "h": 1440, "is_primary": True}
        x, y, w, h = compute_top_center_region(monitor)
        assert x == 853   # 2560 // 3
        assert y == 0
        assert w == 853
        assert h == 720   # 1440 // 2

    def test_region_starts_at_monitor_top(self):
        monitor = {"x": 1920, "y": 100, "w": 1920, "h": 1080, "is_primary": False}
        x, y, w, h = compute_top_center_region(monitor)
        assert y == 100   # monitor's y origin
        assert x == 1920 + 640   # monitor x + w//3

    def test_region_is_top_half(self):
        monitor = {"x": 0, "y": 0, "w": 1920, "h": 1080, "is_primary": True}
        _, _, _, h = compute_top_center_region(monitor)
        assert h == 1080 // 2


# ===========================================================================
# QPopWatcher._prepare_reference_images
# ===========================================================================

class TestPrepareReferenceImages:

    def _make_watcher(self, settings):
        with patch("qpopcv.watcher.get_monitors", return_value=MOCK_MONITORS):
            return QPopWatcher(settings)

    def test_no_reference_path_returns_empty(self):
        s = make_settings(reference_image_paths=[])
        w = self._make_watcher(s)
        assert w._reference_images == []

    def test_nonexistent_path_returns_empty(self, tmp_path):
        missing = tmp_path / "does_not_exist.png"
        s = make_settings(reference_image_paths=[missing])
        w = self._make_watcher(s)
        assert w._reference_images == []

    def test_valid_image_produces_three_scale_variants(self, tmp_path):
        img_path = make_tiny_png(tmp_path)
        s = make_settings(reference_image_paths=[img_path])
        w = self._make_watcher(s)
        assert len(w._reference_images) == 3

    def test_scale_variant_names(self, tmp_path):
        img_path = make_tiny_png(tmp_path)
        s = make_settings(reference_image_paths=[img_path])
        w = self._make_watcher(s)
        names = [name for name, _ in w._reference_images]
        assert "user_ref_0_0.9" in names
        assert "user_ref_0_1.0" in names
        assert "user_ref_0_1.1" in names

    def test_scale_variant_sizes(self, tmp_path):
        img_path = make_tiny_png(tmp_path)
        s = make_settings(reference_image_paths=[img_path])
        w = self._make_watcher(s)
        sizes = {name: img.size for name, img in w._reference_images}
        # 10x10 base
        assert sizes["user_ref_0_1.0"] == (10, 10)
        assert sizes["user_ref_0_0.9"] == (9, 9)   # round(10*0.9)
        assert sizes["user_ref_0_1.1"] == (11, 11)  # round(10*1.1)


# ===========================================================================
# QPopWatcher._check_throttle
# ===========================================================================

class TestCheckThrottle:

    def _make_watcher(self):
        s = make_settings()
        with patch("qpopcv.watcher.get_monitors", return_value=MOCK_MONITORS):
            return QPopWatcher(s)

    def test_not_throttled_initially(self):
        w = self._make_watcher()
        throttled, remaining, _ = w._check_throttle()
        assert throttled is False
        assert remaining == 0

    def test_throttled_immediately_after_detection(self):
        w = self._make_watcher()
        w._last_qpop_time = time.time()
        throttled, remaining, _ = w._check_throttle()
        assert throttled is True
        assert remaining > 0
        assert remaining <= THROTTLE_SECONDS

    def test_not_throttled_after_cooldown(self):
        w = self._make_watcher()
        # Simulate last detection was THROTTLE_SECONDS + 1 ago
        w._last_qpop_time = time.time() - (THROTTLE_SECONDS + 1)
        throttled, _, _ = w._check_throttle()
        assert throttled is False

    def test_throttle_constant_is_15_seconds(self):
        assert THROTTLE_SECONDS == 15


# ===========================================================================
# QPopWatcher start / stop / is_running
# ===========================================================================

class TestWatcherLifecycle:

    def _make_watcher(self):
        s = make_settings()
        with patch("qpopcv.watcher.get_monitors", return_value=MOCK_MONITORS):
            return QPopWatcher(s)

    def test_not_running_before_start(self):
        w = self._make_watcher()
        assert w.is_running() is False

    def test_running_after_start(self):
        w = self._make_watcher()
        # Patch screenshot so the loop doesn't actually do anything
        with patch("qpopcv.watcher.pyautogui.screenshot"), \
             patch("qpopcv.watcher.pyautogui.locate", return_value=None):
            w.start()
            assert w.is_running() is True
            w.stop()

    def test_stop_sets_event(self):
        w = self._make_watcher()
        with patch("qpopcv.watcher.pyautogui.screenshot"), \
             patch("qpopcv.watcher.pyautogui.locate", return_value=None):
            w.start()
            w.stop()
        assert w._stop_event.is_set()

    def test_double_start_does_not_create_second_thread(self):
        w = self._make_watcher()
        with patch("qpopcv.watcher.pyautogui.screenshot"), \
             patch("qpopcv.watcher.pyautogui.locate", return_value=None):
            w.start()
            thread1 = w._thread
            w.start()  # second call should be ignored
            assert w._thread is thread1
            w.stop()


# ===========================================================================
# QPopWatcher._handle_detected_popup  (Discord notification)
# ===========================================================================

class TestHandleDetectedPopup:

    def _make_watcher(self, on_detect=None):
        s = make_settings()
        with patch("qpopcv.watcher.get_monitors", return_value=MOCK_MONITORS):
            return QPopWatcher(s, on_detect=on_detect)

    def test_sends_discord_on_first_detection(self):
        w = self._make_watcher()
        with patch.object(w, "_send_discord_message") as mock_send:
            w._handle_detected_popup("test_ref")
        mock_send.assert_called_once()
        content = mock_send.call_args[0][0]
        assert VALID_USER_ID in content
        assert QUEUE_POP in content

    def test_does_not_send_when_throttled(self):
        w = self._make_watcher()
        w._last_qpop_time = time.time()  # just detected
        with patch.object(w, "_send_discord_message") as mock_send:
            w._handle_detected_popup("test_ref")
        mock_send.assert_not_called()

    def test_calls_on_detect_callback_always(self):
        callback = MagicMock()
        w = self._make_watcher(on_detect=callback)
        with patch.object(w, "_send_discord_message"):
            w._handle_detected_popup("test_ref")
        callback.assert_called_once()

    def test_calls_on_detect_even_when_throttled(self):
        callback = MagicMock()
        w = self._make_watcher(on_detect=callback)
        w._last_qpop_time = time.time()
        with patch.object(w, "_send_discord_message"):
            w._handle_detected_popup("test_ref")
        callback.assert_called_once()

    def test_updates_last_qpop_time_on_send(self):
        w = self._make_watcher()
        before = time.time()
        with patch.object(w, "_send_discord_message"):
            w._handle_detected_popup("test_ref")
        assert w._last_qpop_time >= before

    def test_does_not_update_last_qpop_time_when_throttled(self):
        w = self._make_watcher()
        original_time = time.time() - 5  # 5 seconds ago, within throttle window
        w._last_qpop_time = original_time
        with patch.object(w, "_send_discord_message"):
            w._handle_detected_popup("test_ref")
        # Time should NOT have been updated since it was throttled
        assert w._last_qpop_time == original_time

    def test_mention_format(self):
        w = self._make_watcher()
        with patch.object(w, "_send_discord_message") as mock_send:
            w._handle_detected_popup("test_ref")
        content = mock_send.call_args[0][0]
        assert f"<@{VALID_USER_ID}>" in content
