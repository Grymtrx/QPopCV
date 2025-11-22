# watcher_overlay_test.py

import pyautogui
from PIL import ImageDraw
from watcher import QPopWatcher  # must be in same folder

def main():
    # Minimal config (only needed so QPopWatcher computes region)
    cfg = {
        "webhook_url": "",
        "user_id": "",
        "check_interval": 0.5,
        "confidence": 0.6,
        "ui_scale": 69.0,
    }

    watcher = QPopWatcher(cfg)
    x, y, w, h = watcher._region

    print(f"Region: x={x}, y={y}, w={w}, h={h}")

    # Take full-screen screenshot
    full_img = pyautogui.screenshot()
    draw = ImageDraw.Draw(full_img)

    # Draw the red outline of the watcher region
    draw.rectangle(
        [x, y, x + w - 1, y + h - 1],
        outline="red",
        width=4
    )

    out_path = "qpop_watch_region_overlay.png"
    full_img.save(out_path)

    print(f"Overlay saved to: {out_path}")


if __name__ == "__main__":
    main()
