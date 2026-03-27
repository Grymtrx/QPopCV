"""Tests for AFK notification timer behavior in qpopcv/api.py."""
import pytest
from unittest.mock import patch, MagicMock

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


def make_api(config=None):
    if config is None:
        config = make_config()
    return Api(config, push_event=lambda t, d: None)


# ── _send_afk_notification ─────────────────────────────────────────────────

class TestSendAfkNotification:

    @patch("qpopcv.api.requests.post")
    def test_sends_discord_post_with_mention(self, mock_post):
        api = make_api(make_config())
        api._send_afk_notification()

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        content = kwargs["json"]["content"]
        assert f"<@{VALID_USER_ID}>" in content
        assert "30 minutes" in content

    @patch("qpopcv.api.requests.post")
    def test_no_post_when_webhook_missing(self, mock_post):
        api = make_api(make_config(webhook_url=""))
        api._send_afk_notification()
        mock_post.assert_not_called()

    @patch("qpopcv.api.requests.post")
    def test_no_post_when_user_id_missing(self, mock_post):
        api = make_api(make_config(user_id=""))
        api._send_afk_notification()
        mock_post.assert_not_called()

    @patch("qpopcv.api.requests.post", side_effect=Exception("network error"))
    def test_network_error_does_not_raise(self, mock_post):
        api = make_api()
        api._send_afk_notification()  # must not raise


# ── start_watch / stop_watch timer ────────────────────────────────────────

class TestAfkTimer:

    def _start(self, api, afk_notify, MockWatcher):
        MockWatcher.return_value.oversized_refs = []
        return api.start_watch({
            "webhook_url": VALID_WEBHOOK,
            "user_id": VALID_USER_ID,
            "reference_image_paths": [],
            "monitor_index": 0,
            "afk_notify": afk_notify,
        })

    @patch("qpopcv.api.QPopWatcher")
    @patch("qpopcv.api.threading.Timer")
    def test_timer_created_when_afk_notify_true(self, MockTimer, MockWatcher):
        api = make_api()
        mock_instance = MagicMock()
        MockTimer.return_value = mock_instance
        self._start(api, True, MockWatcher)
        MockTimer.assert_called_once_with(28 * 60, api._send_afk_notification)
        mock_instance.start.assert_called_once()
        assert mock_instance.daemon is True

    @patch("qpopcv.api.QPopWatcher")
    @patch("qpopcv.api.threading.Timer")
    def test_timer_not_created_when_afk_notify_false(self, MockTimer, MockWatcher):
        api = make_api()
        self._start(api, False, MockWatcher)
        MockTimer.assert_not_called()

    @patch("qpopcv.api.QPopWatcher")
    @patch("qpopcv.api.threading.Timer")
    def test_stop_watch_cancels_timer(self, MockTimer, MockWatcher):
        api = make_api()
        mock_instance = MagicMock()
        MockTimer.return_value = mock_instance
        self._start(api, True, MockWatcher)
        api.stop_watch()
        mock_instance.cancel.assert_called_once()
        assert api._afk_timer is None

    def test_stop_watch_without_timer_does_not_raise(self):
        api = make_api()
        api.stop_watch()


# ── get_initial_state ──────────────────────────────────────────────────────

class TestGetInitialStateAfkNotify:

    def test_afk_notify_false_in_initial_state(self):
        api = make_api(make_config(afk_notify=False))
        assert api.get_initial_state()["config"]["afk_notify"] is False

    def test_afk_notify_true_in_initial_state(self):
        api = make_api(make_config(afk_notify=True))
        assert api.get_initial_state()["config"]["afk_notify"] is True


# ── save_config_data ───────────────────────────────────────────────────────

class TestSaveConfigDataAfkNotify:

    @patch("qpopcv.api.save_config")
    def test_afk_notify_persisted(self, mock_save):
        api = make_api()
        api.save_config_data({
            "webhook_url": VALID_WEBHOOK,
            "user_id": VALID_USER_ID,
            "reference_image_paths": [],
            "monitor_index": 0,
            "afk_notify": True,
        })
        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        assert saved.get("afk_notify") is True

    @patch("qpopcv.api.save_config")
    def test_afk_notify_defaults_false(self, mock_save):
        api = make_api()
        api.save_config_data({
            "webhook_url": VALID_WEBHOOK,
            "user_id": VALID_USER_ID,
            "reference_image_paths": [],
            "monitor_index": 0,
        })
        saved = mock_save.call_args[0][0]
        assert saved.get("afk_notify") is False
