# Discord webhook wrapper.
# Sends Discord webhook messages with user mentions.
import requests


def send_discord_mention(
    webhook_url: str,
    user_id: str,
    message: str,
    timeout: float = 5.0,
) -> None:
    
    webhook_url = webhook_url.strip()
    user_id = user_id.strip()

    mention = f"<@{user_id}>"
    payload = {"content": f"{mention} {message}"}

    requests.post(webhook_url, json=payload, timeout=timeout)


def send_test_message(webhook_url: str, user_id: str, timeout: float = 5.0) -> None:
    send_discord_mention(webhook_url, user_id, "connected ✅", timeout=timeout)