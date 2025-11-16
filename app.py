from typing import Dict, Optional
import threading
import time
import webbrowser

import tkinter.messagebox as messagebox
import customtkinter as ctk

from config import (
    APP_DIR,
    APP_VERSION,
    DISCORD_SERVER_URL,
    load_config,
    save_config,
)
from watcher import QPopWatcher, THROTTLE_SECONDS
from updater import UpdateInfo, UpdateManager


class QPopApp:
    def __init__(self) -> None:
        self.config: Dict[str, object] = load_config()
        self._last_test_time: float = 0.0
        self._watcher: Optional[QPopWatcher] = None
        self._update_info: Optional[UpdateInfo] = None
        self._update_clickable: bool = False

        self.update_manager = UpdateManager(
            current_version=APP_VERSION, app_dir=APP_DIR
        )

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title(f"QPopCV {APP_VERSION}")
        self.root.geometry("350x200")
        self.root.minsize(340, 200)
        self.root.resizable(True, True)

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self._build_ui()

        self.root.after(250, self._start_update_check)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # --------- UI BUILDING ---------

    def _build_ui(self) -> None:
        card = ctk.CTkFrame(self.root, corner_radius=16)
        card.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        card.grid_columnconfigure(1, weight=1)

        # Row 0: Webhook
        ctk.CTkLabel(card, text="Discord Webhook:").grid(
            row=0, column=0, padx=6, pady=4, sticky="w"
        )
        self.webhook_var = ctk.StringVar(value=str(self.config.get("webhook_url", "")))
        ctk.CTkEntry(card, textvariable=self.webhook_var, corner_radius=10).grid(
            row=0, column=1, padx=4, pady=4, sticky="we"
        )

        # Row 1: User ID
        ctk.CTkLabel(card, text="Discord User ID:").grid(
            row=1, column=0, padx=6, pady=4, sticky="w"
        )
        self.user_var = ctk.StringVar(value=str(self.config.get("user_id", "")))
        ctk.CTkEntry(card, textvariable=self.user_var, corner_radius=10).grid(
            row=1, column=1, padx=4, pady=4, sticky="we"
        )

        # Row 2: UI Scale
        ctk.CTkLabel(card, text="UI Scale (%):").grid(
            row=2, column=0, padx=6, pady=4, sticky="w"
        )
        self.scale_var = ctk.StringVar(value=str(self.config.get("ui_scale", "69")))
        ctk.CTkEntry(card, textvariable=self.scale_var, corner_radius=10).grid(
            row=2, column=1, padx=4, pady=4, sticky="we"
        )

        # Row 3: Buttons inline
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=3, padx=6, pady=6, sticky="w")

        ctk.CTkButton(
            btn_frame,
            text="Discord 🔗",
            width=80,
            corner_radius=12,
            command=self.on_open_discord,
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            btn_frame,
            text="Test",
            width=70,
            corner_radius=12,
            command=self.on_test_discord,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_frame,
            text="Save",
            width=36,
            corner_radius=12,
            command=self.on_save,
        ).pack(side="left", padx=4)

        self.watch_btn = ctk.CTkButton(
            btn_frame,
            text="Watch",
            width=80,
            corner_radius=12,
            fg_color="#38bdf8",
            hover_color="#0ea5e9",
            command=self.on_toggle_watch,
        )
        self.watch_btn.pack(side="left", padx=4)

        # Row 4: Status
        status_frame = ctk.CTkFrame(card, fg_color="transparent")
        status_frame.grid(row=4, column=0, columnspan=3, padx=6, pady=(0, 4), sticky="we")

        status_frame.grid_columnconfigure(0, weight=0)
        status_frame.grid_columnconfigure(1, weight=1)
        status_frame.grid_columnconfigure(2, weight=0)

        self.status_dot = ctk.CTkLabel(status_frame, text="●", text_color="red")
        self.status_dot.grid(row=0, column=0, padx=(0, 4), sticky="w")

        self.status_label = ctk.CTkLabel(status_frame, text="Status: Stopped")
        self.status_label.grid(row=0, column=1, sticky="w")

        self.update_status_label = ctk.CTkLabel(
            card,
            text="Checking for updates…",
            text_color="gray",
            font=("TkDefaultFont", 11),
        )
        self.update_status_label.grid(
            row=5, column=0, columnspan=2, padx=6, pady=(4, 4), sticky="w"
        )
        self.update_status_label.bind("<Button-1>", self.on_update_click)

    # --------- CONFIG / VALIDATION ---------

    def _update_config_from_ui(self) -> None:
        self.config["webhook_url"] = self.webhook_var.get().strip()
        self.config["user_id"] = self.user_var.get().strip()
        self.config["ui_scale"] = self.scale_var.get().strip()

    def _normalize_ui_scale_in_config(self) -> None:
        try:
            value = float(self.config.get("ui_scale", 69))
        except (TypeError, ValueError):
            value = 69.0
        self.config["ui_scale"] = value

    @staticmethod
    def _validate_discord_settings(
        webhook_url: str, user_id: str, ui_scale: str
    ) -> bool:
        if not webhook_url.strip():
            messagebox.showwarning(
                "Missing Discord Webhook URL",
                "Please set the Discord Webhook URL.",
            )
            return False
        if not user_id.strip():
            messagebox.showwarning(
                "Missing Discord user ID",
                "Please set the Discord user ID.",
            )
            return False
        if not (user_id.isdigit() and len(user_id) == 18):
            messagebox.showwarning(
                "Invalid Discord user ID",
                "Discord user IDs contain exactly 18 digits (example: 695333359080964166).",
            )
            return False
        try:
            scale_value = float(ui_scale)
        except (TypeError, ValueError):
            messagebox.showwarning(
                "Invalid UI Scale %",
                "Please enter a valid UI Scale percentage between 65 and 115.",
            )
            return False
        if not (65 <= scale_value <= 115):
            messagebox.showwarning(
                "Invalid UI Scale %",
                "Please enter a valid UI Scale percentage between 65 and 115.",
            )
            return False
        return True

    # --------- BUTTON HANDLERS ---------

    def on_save(self) -> None:
        self._update_config_from_ui()
        if not self._validate_discord_settings(
            str(self.config["webhook_url"]),
            str(self.config["user_id"]),
            str(self.config["ui_scale"]),
        ):
            return

        self._normalize_ui_scale_in_config()
        save_config(self.config)
        messagebox.showinfo("Saved", "Configuration saved.")

    def on_test_discord(self) -> None:
        throttled, remaining, now = self._check_test_throttle()
        if throttled:
            messagebox.showwarning(
                "Throttled",
                f"Please wait {remaining} seconds before sending another test.",
            )
            return

        webhook_url = self.webhook_var.get().strip()
        user_id = self.user_var.get().strip()

        ui_scale = self.scale_var.get().strip()

        if not self._validate_discord_settings(webhook_url, user_id, ui_scale):
            return

        import requests  # local import to keep watcher.py self-contained

        mention = f"<@{user_id}>"
        try:
            requests.post(
                webhook_url,
                json={
                    "content": f"{mention} connected ✅"
                },
                timeout=5,
            )
            self._last_test_time = now
            messagebox.showinfo("Success", "Test message sent to Discord.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send test message:\n{e}")

    def on_open_discord(self) -> None:
        webbrowser.open(DISCORD_SERVER_URL)

    def on_toggle_watch(self) -> None:
        if self._watcher is None or not self._watcher.is_running():
            self._start_watch()
        else:
            self._stop_watch()

    def on_update_click(self, _event=None) -> None:
        if not self._update_clickable:
            messagebox.showinfo("QPopCV", "You are running the latest version.")
            return

        if not self._update_info or not self._update_info.available:
            messagebox.showinfo("QPopCV", "No update is currently available.")
            return

        if not messagebox.askyesno(
            "Update Available",
            f"Version {self._update_info.latest_version} is available.\n"
            "Would you like to download and install it now?",
        ):
            return

        self._set_update_status("Downloading update…", clickable=False, color="#0ea5e9")
        threading.Thread(
            target=self._perform_update_install, daemon=True
        ).start()

    # --------- WATCHER CONTROL ---------

    def _start_watch(self) -> None:
        self._update_config_from_ui()

        if not self._validate_discord_settings(
            str(self.config["webhook_url"]),
            str(self.config["user_id"]),
            str(self.config["ui_scale"]),
        ):
            return

        messagebox.showinfo(
            "Mobile Discord Notifications",
            "If you would like Discord Notifications to be directed to your phone "
            "INSTEAD of your PC, please 'Quit Discord' in your system tray.",
        )

        self._normalize_ui_scale_in_config()
        save_config(self.config)

        self._watcher = QPopWatcher(self.config, on_detect=self._flash_detected_status)
        self._watcher.start()

        self.status_label.configure(text="Status: Watching")
        self.status_dot.configure(text_color="green")
        self.watch_btn.configure(text="Stop", fg_color="#0ea5e9")

    def _stop_watch(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()

        self.status_label.configure(text="Status: Stopped")
        self.status_dot.configure(text_color="red")
        self.watch_btn.configure(text="Watch", fg_color="#38bdf8")

    def _flash_detected_status(self) -> None:
        """Flash 'Detected!' for 2 seconds, then restore previous state."""
        prev_text = self.status_label.cget("text")
        prev_color = self.status_dot.cget("text_color")

        self.status_label.configure(text="Status: Detected!")
        self.status_dot.configure(text_color="orange")

        def restore():
            self.status_label.configure(text=prev_text)
            self.status_dot.configure(text_color=prev_color)

        self.status_label.after(2000, restore)

    def _check_test_throttle(self):
        now = time.time()
        elapsed = now - self._last_test_time
        if elapsed < THROTTLE_SECONDS:
            remaining = int(THROTTLE_SECONDS - elapsed)
            return True, remaining, now
        return False, 0, now

    # --------- LIFECYCLE ---------

    def _start_update_check(self) -> None:
        threading.Thread(target=self._check_updates_background, daemon=True).start()

    def _check_updates_background(self) -> None:
        try:
            info = self.update_manager.check_for_updates()
        except Exception as exc:
            print("Update check failed:", exc)
            self.root.after(
                0,
                lambda: self._set_update_status(
                    "Update check failed", clickable=False, color="red"
                ),
            )
            return

        self._update_info = info
        self.root.after(0, lambda: self._apply_update_info(info))

    def _apply_update_info(self, info: UpdateInfo) -> None:
        if info.available:
            text = f"Update available: {info.latest_version} (click to install)"
            self._set_update_status(text, clickable=True, color="#0ea5e9")
        else:
            text = f"Version {APP_VERSION} is up to date"
            self._set_update_status(text, clickable=False, color="gray")

    def _set_update_status(self, text: str, clickable: bool, color: str = "gray") -> None:
        self.update_status_label.configure(text=text, text_color=color)
        self._update_clickable = clickable
        cursor = "hand2" if clickable else "arrow"
        self.update_status_label.configure(cursor=cursor)

    def _perform_update_install(self) -> None:
        try:
            assert self._update_info is not None
            self.update_manager.install_update(self._update_info)
        except Exception as exc:
            print("Update installation failed:", exc)
            self.root.after(
                0,
                lambda: self._set_update_status(
                    "Update failed – try again", clickable=True, color="red"
                ),
            )
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Update Failed", f"Unable to install the update:\n{exc}"
                ),
            )
            return

        self.root.after(0, self._restart_after_update)

    def _restart_after_update(self) -> None:
        messagebox.showinfo(
            "Update Installed",
            "The newest version has been installed. QPopCV will relaunch now.",
        )
        self.on_close()
        self.update_manager.relaunch()

    def on_close(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = QPopApp()
    app.run()


if __name__ == "__main__":
    main()
