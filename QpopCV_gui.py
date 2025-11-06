import json
import threading
import time
import requests
import webbrowser
from pathlib import Path
import pyautogui
from pyautogui import ImageNotFoundException
import tkinter.messagebox as messagebox
import customtkinter as ctk

APP_VERSION = "V1.0.0"
CONFIG_PATH = Path("config.json")
DISCORD_SERVER_URL = "https://discord.gg/Tg4myXwf"

stop_event = threading.Event()
watcher_thread = None

# ------------ throttle control ------------
last_test_time = 0        # limits how often "Test" can be used
last_qpop_time = 0        # limits how often Qpop! webhook is sent
THROTTLE_SECONDS = 15

# ------------ config helpers ------------

def load_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "webhook_url": "",
        "user_id": "",
        "check_interval": 0.5,
        "confidence": 0.6,
    }

def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

# ------------ watcher logic (screen-based) ------------

REFERENCE_IMG = [
    ("solo_shuffle_blizzui", Path("media/qpop_ss_blizzardUI_reference.png")),
    ("solo_shuffle_bbqui", Path("media/qpop_ss_bbq_reference.png")),
    ("solo_shuffle_bbqui_dark", Path("media/qpop_ss_bbq_dark_reference.png")),
    # ("additional_ref_img", Path("media/additional_ref_img.png")),
]

def start_watcher(cfg, status_label, status_dot):
    global watcher_thread, stop_event
    if watcher_thread and watcher_thread.is_alive():
        return  # already running

    url = cfg.get("webhook_url", "").strip()
    uid = cfg.get("user_id", "").strip()
    if not url or not uid:
        messagebox.showwarning("Missing settings", "Webhook URL and Discord User ID are required.")
        return

    stop_event.clear()

    check_interval = float(cfg.get("check_interval", 0.5))
    confidence = float(cfg.get("confidence", 0.6))
    mention = f"<@{uid}>"

    # compute region: top-center slice of the screen
    screen_w, screen_h = pyautogui.size()
    region_x = int(screen_w / 3)
    region_y = 0
    region_w = int(screen_w / 3)
    region_h = int(screen_h / 2)
    region = (region_x, region_y, region_w, region_h)

    print("QPopCV screen watcher started.")
    print(f"Region (top-center): {region}")
    print(f"Interval: {check_interval}s, confidence: {confidence}")

    for name, path in REFERENCE_IMG:
        if not path.exists():
            print(f"⚠ Missing reference image for '{name}': {path}")

    # helper to flash "Detected!" for 2 seconds, then restore previous state
    def flash_detected():
        prev_text = status_label.cget("text")
        prev_color = status_dot.cget("text_color")
        status_label.configure(text="Status: Detected!")
        status_dot.configure(text_color="orange")
        # after 2 seconds, restore previous
        status_label.after(
            2000,
            lambda: (
                status_label.configure(text=prev_text),
                status_dot.configure(text_color=prev_color),
            ),
        )

    def loop():
        global last_qpop_time
        seen_once = False
        while not stop_event.is_set():
            try:
                match_found = False
                match_name = None

                for name, path in REFERENCE_IMG:
                    if not path.exists():
                        continue
                    try:
                        loc = pyautogui.locateOnScreen(
                            str(path),
                            confidence=confidence,
                            region=region,
                        )
                    except ImageNotFoundException:
                        loc = None

                    if loc is not None:
                        match_found = True
                        match_name = name
                        break

                if match_found and not seen_once:
                    ts = time.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{ts}] Queue popup detected via '{match_name}'")

                    now = time.time()
                    if now - last_qpop_time >= THROTTLE_SECONDS:
                        try:
                            requests.post(
                                url,
                                json={"content": f"{mention} Qpop!"},
                                timeout=5,
                            )
                            last_qpop_time = now
                            print("Discord notification sent.")
                        except Exception as e:
                            print("Error sending webhook:", e)
                    else:
                        remaining = int(THROTTLE_SECONDS - (now - last_qpop_time))
                        print(f"⏳ Qpop! throttled — skipping (wait {remaining}s).")

                    # flash detected state in GUI
                    flash_detected()
                    seen_once = True

                elif not match_found and seen_once:
                    print("Popup gone, ready for next detection.")
                    seen_once = False

                if stop_event.wait(check_interval):
                    break
            except Exception as e:
                print("Watcher error:", e)
                if stop_event.wait(2):
                    break

        print("Watcher stopped.")

    watcher_thread = threading.Thread(target=loop, daemon=True)
    watcher_thread.start()
    status_label.configure(text="Status: Watching")
    status_dot.configure(text_color="green")

def stop_watcher(status_label, status_dot):
    global watcher_thread, stop_event
    stop_event.set()
    status_label.configure(text="Status: Stopped")
    status_dot.configure(text_color="red")

# ------------ main GUI ------------

def main():
    cfg = load_config()

    ctk.set_appearance_mode("light")          # "light", "dark", "system"
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title(f"QPopCV {APP_VERSION}")
    root.geometry("360x180")
    root.minsize(340, 170)
    root.resizable(True, True)

    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)

    card = ctk.CTkFrame(root, corner_radius=16)
    card.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

    card.grid_columnconfigure(1, weight=1)

    # Row 0: Webhook
    ctk.CTkLabel(card, text="Webhook:").grid(row=0, column=0, padx=6, pady=4, sticky="w")
    webhook_var = ctk.StringVar(value=cfg.get("webhook_url", ""))
    ctk.CTkEntry(card, textvariable=webhook_var, corner_radius=10).grid(
        row=0, column=1, padx=4, pady=4, sticky="we"
    )

    # Row 1: User ID
    ctk.CTkLabel(card, text="User ID:").grid(row=1, column=0, padx=6, pady=4, sticky="w")
    user_var = ctk.StringVar(value=cfg.get("user_id", ""))
    ctk.CTkEntry(card, textvariable=user_var, corner_radius=10).grid(
        row=1, column=1, padx=4, pady=4, sticky="we"
    )

    # Row 2: Buttons inline
    def on_save():
        cfg["webhook_url"] = webhook_var.get().strip()
        cfg["user_id"] = user_var.get().strip()
        if not cfg["webhook_url"]:
            messagebox.showwarning("Missing webhook", "Please set the Discord webhook URL.")
            return
        if not cfg["user_id"]:
            messagebox.showwarning("Missing user ID", "Please set the Discord user ID.")
            return
        save_config(cfg)
        messagebox.showinfo("Saved", "Configuration saved.")

    def on_test_discord():
        global last_test_time
        now = time.time()
        if now - last_test_time < THROTTLE_SECONDS:
            remaining = int(THROTTLE_SECONDS - (now - last_test_time))
            messagebox.showwarning(
                "Throttled",
                f"Please wait {remaining} seconds before sending another test."
            )
            return

        test_url = webhook_var.get().strip()
        test_uid = user_var.get().strip()
        if not test_url or not test_uid:
            messagebox.showwarning("Missing settings", "Webhook URL and User ID are required for test.")
            return

        mention = f"<@{test_uid}>"
        try:
            requests.post(
                test_url,
                json={"content": f"{mention} QPop App Discord Connection Test ✅"},
                timeout=5,
            )
            last_test_time = now
            messagebox.showinfo("Success", "Test message sent to Discord.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send test message:\n{e}")

    def on_open_discord():
        webbrowser.open(DISCORD_SERVER_URL)

    btn_frame = ctk.CTkFrame(card, fg_color="transparent")
    btn_frame.grid(row=2, column=0, columnspan=3, padx=6, pady=6, sticky="w")

    discord_btn = ctk.CTkButton(
        btn_frame,
        text="Discord",
        width=70,
        corner_radius=12,
        command=on_open_discord,
    )
    discord_btn.pack(side="left", padx=(0, 4))

    save_btn = ctk.CTkButton(
        btn_frame,
        text="💾",
        width=36,
        corner_radius=12,
        command=on_save,
    )
    save_btn.pack(side="left", padx=4)

    test_btn = ctk.CTkButton(
        btn_frame,
        text="Test",
        width=70,
        corner_radius=12,
        command=on_test_discord,
    )
    test_btn.pack(side="left", padx=4)

    watch_state = {"running": False}

    def toggle_watch():
        if not watch_state["running"]:
            cfg["webhook_url"] = webhook_var.get().strip()
            cfg["user_id"] = user_var.get().strip()
            if not (cfg["webhook_url"] and cfg["user_id"]):
                messagebox.showwarning(
                    "Missing settings",
                    "Please fill in webhook and Discord user ID before watching."
                )
                return

            messagebox.showinfo(
                "Mobile Discord Notifications",
                "If you would like Discord notifications to be directed to your phone, "
                "please close Discord and 'Quit Discord' in your system tray."
            )

            save_config(cfg)
            start_watcher(cfg, status_label, status_dot)
            watch_btn.configure(text="Stop", fg_color="#0ea5e9")
            watch_state["running"] = True
        else:
            stop_watcher(status_label, status_dot)
            watch_btn.configure(text="Watch", fg_color="#38bdf8")
            watch_state["running"] = False

    watch_btn = ctk.CTkButton(
        btn_frame,
        text="Watch",
        width=80,
        corner_radius=12,
        fg_color="#38bdf8",
        hover_color="#0ea5e9",
        command=toggle_watch,
    )
    watch_btn.pack(side="left", padx=4)

    # Row 3: Status + version
    status_frame = ctk.CTkFrame(card, fg_color="transparent")
    status_frame.grid(row=3, column=0, columnspan=3, padx=6, pady=(0, 4), sticky="we")

    status_frame.grid_columnconfigure(0, weight=0)
    status_frame.grid_columnconfigure(1, weight=1)
    status_frame.grid_columnconfigure(2, weight=0)

    status_dot = ctk.CTkLabel(status_frame, text="●", text_color="red")
    status_dot.grid(row=0, column=0, padx=(0, 4), sticky="w")

    status_label = ctk.CTkLabel(status_frame, text="Status: Stopped")
    status_label.grid(row=0, column=1, sticky="w")

    def on_close():
        stop_watcher(status_label, status_dot)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    main()
