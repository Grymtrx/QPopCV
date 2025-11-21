from pathlib import Path
from typing import Dict
import json
import sys

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).resolve().parent

APP_VERSION = "1.0.3"
CONFIG_PATH = APP_DIR / "config.json"
DISCORD_SERVER_URL = "https://discord.gg/vXvjcrUFm8"  # QPopCV Discord Server (PermaLink)

DEFAULT_CONFIG: Dict[str, object] = {
    "webhook_url": "https://discord.com/api/webhooks/1435435868767912096/Ken8UDwQGDKEZ-MJAo6FNQR9wNxOahRgg5Pci_Y2X-smeSKUeE4dfhYuwfkCKu1hmzVA",
    "user_id": "",
    "check_interval": 0.15,
    "confidence": 0.6,
    # NEW: per-user reference image path, captured on *their* PC
    "reference_image_path": "",
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
