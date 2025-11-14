from pathlib import Path
from typing import Dict
import json

APP_VERSION = "V1.0.0"
CONFIG_PATH = Path("config.json")
DISCORD_SERVER_URL = "https://discord.gg/vXvjcrUFm8"  # QPopCV Discord Server (PermaLink)

DEFAULT_CONFIG: Dict[str, object] = {
    "webhook_url": "",
    "user_id": "",
    "check_interval": 0.5,
    "confidence": 0.6,
}


def load_config() -> Dict[str, object]:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            return merged
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, object]) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")