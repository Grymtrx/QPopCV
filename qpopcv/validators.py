
# Validation helpers for QPopCV Watcher App inputs (Discord + Reference image).

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

    if not user_id:
        messagebox.showwarning(
            "Missing Discord user ID",
            "Please set the Discord user ID.",
        )
        return False

    if not (user_id.isdigit() and len(user_id) == 18):
        messagebox.showwarning(
            "Invalid Discord user ID",
            "Please enter Discord user ID NOT username.",
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
