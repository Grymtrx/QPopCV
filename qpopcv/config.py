from pathlib import Path
from typing import Dict
import json
import logging
import sys

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
    _MEDIA_ROOT = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parent
    _MEDIA_ROOT = APP_DIR

MEDIA_DIR = _MEDIA_ROOT / "media"
FONTS_DIR = _MEDIA_ROOT / "fonts"

logger = logging.getLogger(__name__)

APP_VERSION = "1.1.2"
# config.json  — tracked in git; contains shared defaults (webhook URL only)
# config.local.json — gitignored; contains the user's personal settings
BASE_CONFIG_PATH = APP_DIR / "config.json"
USER_CONFIG_PATH = APP_DIR / "config.local.json"
DISCORD_SERVER_URL = "https://discord.gg/KpupS6N3Zj"  # QPopCV Discord Server (PermaLink)

DEFAULT_CONFIG: Dict[str, object] = {
    "webhook_url": "https://discord.com/api/webhooks/1435435868767912096/Ken8UDwQGDKEZ-MJAo6FNQR9wNxOahRgg5Pci_Y2X-smeSKUeE4dfhYuwfkCKu1hmzVA",
    "user_id": "",
    "check_interval": 0.15,
    "confidence": 0.6,
    "reference_image_paths": [],
    "monitor_index": 0,
    "afk_notify": False,
}


def _load_json(path: Path) -> Dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return {}


def load_config() -> Dict[str, object]:
    merged = DEFAULT_CONFIG.copy()

    # Layer 1: shared base config from repo (webhook URL etc.)
    if BASE_CONFIG_PATH.exists():
        merged.update(_load_json(BASE_CONFIG_PATH))

    # Layer 2: user's personal config (overlays everything)
    if USER_CONFIG_PATH.exists():
        merged.update(_load_json(USER_CONFIG_PATH))

    # Migrate old single-path key to list
    old_path = str(merged.pop("reference_image_path", "") or "").strip()
    if old_path and not merged.get("reference_image_paths"):
        merged["reference_image_paths"] = [old_path]

    return merged


def save_config(config: Dict[str, object]) -> None:
    """Save user settings to config.local.json (never touches config.json)."""
    USER_CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")