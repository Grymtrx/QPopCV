"""Tests for AFK reset, escalation, and session tracking in qpopcv/api.py."""
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime

from qpopcv.api import Api

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


def make_api(config=None, push_event=None):
    if config is None:
        config = make_config()
    if push_event is None:
        push_event = MagicMock()
    return Api(config, push_event=push_event)


class TestAfkEscalation:

    @patch("qpopcv.api.requests.post")
    def test_send_afk_warning_pushes_sse_event(self, mock_post):
        push = MagicMock()
        api = make_api(push_event=push)
        api._send_afk_warning()
        push.assert_any_call("afk_warning", None)

    @patch("qpopcv.api.requests.post")
    def test_send_afk_warning_sends_discord_message(self, mock_post):
        api = make_api()
        api._send_afk_warning()
        mock_post.assert_called_once()
        content = mock_post.call_args[1]["json"]["content"]
        assert "Move character to prevent AFK logout" in content
        assert f"<@{VALID_USER_ID}>" in content

    @patch("qpopcv.api.requests.post")
    def test_send_afk_warning_creates_escalation_timer(self, mock_post):
        api = make_api()
        api._send_afk_warning()
        assert api._afk_escalation_timer is not None

    @patch("qpopcv.api.requests.post")
    def test_send_afk_logout_sends_second_discord(self, mock_post):
        api = make_api()
        api._send_afk_logout()
        mock_post.assert_called_once()
        content = mock_post.call_args[1]["json"]["content"]
        assert "auto-logged out" in content

    @patch("qpopcv.api.requests.post")
    def test_send_afk_logout_pushes_sse_event(self, mock_post):
        push = MagicMock()
        api = make_api(push_event=push)
        api._send_afk_logout()
        push.assert_any_call("afk_logout", None)


class TestAfkReset:

    @patch("qpopcv.api.threading.Timer")
    def test_reset_afk_restarts_timer(self, MockTimer):
        push = MagicMock()
        api = make_api(make_config(afk_notify=True), push_event=push)
        api._afk_warned = True
        mock_esc = MagicMock()
        api._afk_escalation_timer = mock_esc
        result = api.reset_afk()
        assert result["ok"] is True
        mock_esc.cancel.assert_called_once()
        MockTimer.assert_called_once()
        push.assert_any_call("afk_reset", None)

    def test_reset_afk_when_not_warned_returns_error(self):
        api = make_api()
        api._afk_warned = False
        result = api.reset_afk()
        assert result["ok"] is False


class TestSessionTracking:

    @patch("qpopcv.api._validate_ref_images", return_value=None)
    @patch("qpopcv.api.QPopWatcher")
    @patch("qpopcv.api._is_discord_running", return_value=False)
    def test_start_watch_records_session_start(self, _dc, MockWatcher, _val):
        api = make_api()
        MockWatcher.return_value.oversized_refs = []
        api.start_watch({
            "webhook_url": VALID_WEBHOOK,
            "user_id": VALID_USER_ID,
            "reference_image_paths": [],
            "monitor_index": 0,
            "afk_notify": False,
        })
        assert api._session_start_time is not None
        assert api._session_paused_total == 0.0

    @patch("qpopcv.api._validate_ref_images", return_value=None)
    @patch("qpopcv.api.QPopWatcher")
    @patch("qpopcv.api._is_discord_running", return_value=False)
    def test_stop_watch_records_session(self, _dc, MockWatcher, _val):
        api = make_api()
        MockWatcher.return_value.oversized_refs = []
        api.start_watch({
            "webhook_url": VALID_WEBHOOK,
            "user_id": VALID_USER_ID,
            "reference_image_paths": [],
            "monitor_index": 0,
            "afk_notify": False,
        })
        result = api.stop_watch()
        assert result["ok"] is True
        assert "session" in result
        assert result["session"]["detected"] is False
        assert result["session"]["duration_seconds"] >= 0
