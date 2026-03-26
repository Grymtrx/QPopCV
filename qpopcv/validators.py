
# Validation helpers for QPopCV Watcher App inputs (Discord + Reference image + region).

from pathlib import Path
import tkinter.messagebox as messagebox


def validate_discord_core(webhook_url: str, user_id: str) -> bool:
    # Validate webhook URL + Discord user ID, showing message boxes on error.
    webhook_url = webhook_url.strip()
    user_id = user_id.strip()

    if not webhook_url:
        messagebox.showwarning(
            "Missing Discord Webhook URL",
            "Please set the Discord Webhook URL.",
        )
        return False

    if not webhook_url.startswith("https://discord.com/api/webhooks/"):
        messagebox.showwarning(
            "Invalid Discord Webhook URL",
            "Webhook URL must start with https://discord.com/api/webhooks/",
        )
        return False

    if not user_id:
        messagebox.showwarning(
            "Missing Discord user ID",
            "Please set the Discord user ID.",
        )
        return False

    if not (user_id.isdigit() and 17 <= len(user_id) <= 19):
        messagebox.showwarning(
            "Invalid Discord user ID",
            "Please enter Discord user ID NOT username.",
        )
        return False

    return True


def validate_watch_region(region_str: str) -> bool:
    # Empty = auto-compute (always valid).
    region_str = region_str.strip()
    if not region_str:
        return True

    parts = region_str.split(",")
    if len(parts) != 4:
        messagebox.showwarning(
            "Invalid Watch Region",
            "Watch Region must be empty (auto) or exactly four comma-separated integers: x,y,w,h\n\n"
            "Example: 1920,0,960,540",
        )
        return False

    try:
        x, y, w, h = (int(p.strip()) for p in parts)
    except ValueError:
        messagebox.showwarning(
            "Invalid Watch Region",
            "All four Watch Region values must be integers.\n\n"
            "Example: 1920,0,960,540",
        )
        return False

    if w <= 0 or h <= 0:
        messagebox.showwarning(
            "Invalid Watch Region",
            "Watch Region width and height must be greater than zero.",
        )
        return False

    return True


def validate_reference_image(path_str: str) -> bool:
    # Validate that the reference image path is a valid file.
    path_str = path_str.strip()
    path = Path(path_str).expanduser()

    if not path_str or not path.exists() or path.is_dir():
        messagebox.showwarning(
            "Reference Image Error",
            "Please select a valid reference image file of your WoW queue popup.",
        )
        return False

    return True
