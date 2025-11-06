import json
import time
import requests
import pyautogui
from pyautogui import ImageNotFoundException
from pathlib import Path

# --- LOAD CONFIG ---
cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
WEBHOOK_URL = cfg["webhook_url"]
USER_ID = cfg["user_id"]
MENTION = f"<@{USER_ID}>"
CHECK_INTERVAL = float(cfg.get("check_interval", 0.5))
CONFIDENCE = float(cfg.get("confidence", 0.6))


# --- REFERENCE IMAGES ---
REFERENCE_IMG = [
    ("solo_shuffle_blizzui", Path("media/qpop_ss_blizzardUI_reference.png")),
    ("solo_shuffle_bbqui", Path("media/qpop_ss_bbq_reference.png")),
    ("solo_shuffle_bbqui_dark", Path("media/qpop_ss_bbq_dark_reference.png")),
    # ("additional_ref_img", Path("media/additional_ref_img.png")),
]
 

# --- CAPTURE REGION ---
# Get screen size
screen_w, screen_h = pyautogui.size()

# Top-center 1/3 of the screen
region_x = int(screen_w / 3)        # start at 1/3 from the left
region_y = 0                        # top of the screen
region_w = int(screen_w / 3)        # width = 1/3 of screen width
region_h = int(screen_h / 2)        # height = 1/2 of screen height
region = (region_x, region_y, region_w, region_h)
print("QPopCV watching for SS PvP Queue Popup...")
print(f"Scanning region (top center): {region}")

# --- MAIN LOOP ---
seen_once = False

while True:
    try:
        match_found = False
        match_name = None

        for name, path in REFERENCE_IMG:
            try:
                loc = pyautogui.locateOnScreen(str(path), confidence=CONFIDENCE, region=region)
            except ImageNotFoundException:
                loc = None

            if loc is not None:
                match_found = True
                match_name = name
                break

        if match_found and not seen_once:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] Queue popup detected via '{match_name}'")
            try:
                requests.post(WEBHOOK_URL, json={"content": f"{MENTION} Qpop!"}, timeout=5) 
                print("Discord notification sent.")
            except Exception as e:
                print("Error sending webhook:", e)
            seen_once = True
        elif not match_found and seen_once:
            print("Popup gone, ready for next detection.")
            seen_once = False

        time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\nStopped by user.")
        break
    except Exception as e:
        print("Error:", e)
        time.sleep(1)