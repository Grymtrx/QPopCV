# QPopCV proxy client. Sends notifications via the Cloudflare Worker proxy
# at config.PROXY_URL. The real Discord webhook URL is a worker secret,
# never exposed to the app.
import logging
import requests
from .config import PROXY_URL

logger = logging.getLogger(__name__)


def notify(user_id: str, type_: str, timeout: float = 5.0) -> None:
    """Fire-and-forget notify. Logs errors instead of raising — used by the
    watcher and AFK timers, where network failures shouldn't crash the app."""
    user_id = user_id.strip()
    if not user_id:
        return
    try:
        requests.post(
            PROXY_URL,
            json={"user_id": user_id, "type": type_},
            timeout=timeout,
        )
    except Exception as exc:
        logger.error("Proxy notify failed (type=%s): %s", type_, exc)


def send_test_message(user_id: str, timeout: float = 5.0) -> None:
    """Raises on failure so the UI can surface the error."""
    user_id = user_id.strip()
    resp = requests.post(
        PROXY_URL,
        json={"user_id": user_id, "type": "test"},
        timeout=timeout,
    )
    resp.raise_for_status()
