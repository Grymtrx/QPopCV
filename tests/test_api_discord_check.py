"""Tests for Discord process detection in qpopcv/api.py."""
import pytest
from unittest.mock import patch, MagicMock

from qpopcv.api import Api, _is_discord_running

VALID_WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/token"
VALID_USER_ID = "123456789012345678"


def make_config(**overrides):
    base = {
        "webhook_url": VALID_WEBHOOK,
        "user_id": VALID_USER_ID,
        "reference_image_paths": [],
        "monitor_index": 0,
        "afk_notify": False,
    }
    base.update(overrides)
    return base


def make_api(config=None):
    if config is None:
        config = make_config()
    return Api(config, push_event=lambda t, d: None)


# ── _is_discord_running ────────────────────────────────────────────────────

class TestIsDiscordRunning:

    @patch("qpopcv.api.psutil.process_iter")
    def test_returns_true_when_discord_running(self, mock_iter):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "Discord.exe"
        mock_iter.return_value = [mock_proc]
        assert _is_discord_running() is True

    @patch("qpopcv.api.psutil.process_iter")
    def test_returns_false_when_discord_not_running(self, mock_iter):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "chrome.exe"
        mock_iter.return_value = [mock_proc]
        assert _is_discord_running() is False

    @patch("qpopcv.api.psutil.process_iter")
    def test_case_insensitive_match(self, mock_iter):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "DISCORD.EXE"
        mock_iter.return_value = [mock_proc]
        assert _is_discord_running() is True

    @patch("qpopcv.api.psutil.process_iter")
    def test_returns_false_when_no_processes(self, mock_iter):
        mock_iter.return_value = []
        assert _is_discord_running() is False


# ── kill_discord ──────────────────────────────────────────────────────────

class TestKillDiscord:

    @patch("qpopcv.api.psutil.process_iter")
    def test_terminates_discord_processes(self, mock_iter):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "Discord.exe"
        mock_iter.return_value = [mock_proc]
        api = make_api()
        result = api.kill_discord()
        mock_proc.terminate.assert_called_once()
        assert result["ok"] is True

    @patch("qpopcv.api.psutil.process_iter")
    def test_skips_non_discord_processes(self, mock_iter):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "chrome.exe"
        mock_iter.return_value = [mock_proc]
        api = make_api()
        result = api.kill_discord()
        mock_proc.terminate.assert_not_called()
        assert result["ok"] is True

    @patch("qpopcv.api.psutil.process_iter", side_effect=Exception("unexpected OS error"))
    def test_returns_error_on_unexpected_exception(self, _mock_iter):
        api = make_api()
        result = api.kill_discord()
        assert result["ok"] is False
        assert "error" in result


# ── start_watch discord check ─────────────────────────────────────────────

class TestStartWatchDiscordCheck:

    def _start(self, api, MockWatcher, skip=False):
        MockWatcher.return_value.oversized_refs = []
        return api.start_watch({
            "webhook_url": VALID_WEBHOOK,
            "user_id": VALID_USER_ID,
            "reference_image_paths": [],
            "monitor_index": 0,
            "afk_notify": False,
            "skip_discord_check": skip,
        })

    @patch("qpopcv.api.save_config")
    @patch("qpopcv.api._validate_ref_images", return_value=None)
    @patch("qpopcv.api.QPopWatcher")
    @patch("qpopcv.api._is_discord_running", return_value=True)
    def test_returns_discord_running_when_detected(self, _dc, MockWatcher, _val, _save):
        api = make_api()
        result = self._start(api, MockWatcher, skip=False)
        assert result["ok"] is False
        assert result.get("discord_running") is True

    @patch("qpopcv.api.save_config")
    @patch("qpopcv.api._validate_ref_images", return_value=None)
    @patch("qpopcv.api.QPopWatcher")
    @patch("qpopcv.api._is_discord_running", return_value=True)
    def test_skip_flag_bypasses_discord_check(self, _dc, MockWatcher, _val, _save):
        api = make_api()
        result = self._start(api, MockWatcher, skip=True)
        assert result["ok"] is True

    @patch("qpopcv.api.save_config")
    @patch("qpopcv.api._validate_ref_images", return_value=None)
    @patch("qpopcv.api.QPopWatcher")
    @patch("qpopcv.api._is_discord_running", return_value=False)
    def test_proceeds_when_discord_not_running(self, _dc, MockWatcher, _val, _save):
        api = make_api()
        result = self._start(api, MockWatcher, skip=False)
        assert result["ok"] is True
