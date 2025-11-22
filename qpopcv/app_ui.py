from typing import Dict, Optional
import threading
import time
import webbrowser
from pathlib import Path

from tkinter import filedialog
import tkinter.messagebox as messagebox
import customtkinter as ctk

from .config import (
    APP_DIR,
    APP_VERSION,
    DISCORD_SERVER_URL,
    load_config,
    save_config,
)
from .watcher import QPopWatcher, THROTTLE_SECONDS, WatcherSettings
from .updater import UpdateInfo, UpdateManager
from .theme import (
    BG_COLOR,
    CARD_BG,
    CARD_BORDER,
    ACCENT,
    ACCENT_HOVER,
    TEXT_PRIMARY,
    TEXT_MUTED,
    DANGER,
    SUCCESS,
    DETECTED,
)
from .validators import validate_discord_core, validate_reference_image
from .discord_client import send_test_message


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
        # Window title
        self.root.title("QPopCV Watcher App")
        self.root.geometry("360x220")
        self.root.minsize(360, 220)
        self.root.resizable(True, True)
        self.root.configure(fg_color=BG_COLOR)

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=0)

        self._build_ui()

        self.root.after(250, self._start_update_check)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # --------- UI BUILDING ---------

    def _build_ui(self) -> None:

        card = ctk.CTkFrame(
            self.root,
            corner_radius=14,
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
        )
        card.grid(row=0, column=0, padx=8, pady=8 , sticky="new")

        card.grid_columnconfigure(0, weight=0)
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(2, weight=0)

        # Row 0: Webhook (extra top padding)
        ctk.CTkLabel(
            card,
            text="Discord Webhook",
            text_color=TEXT_PRIMARY,
            font=("Segoe UI", 10),
        ).grid(row=0, column=0, padx=6, pady=(10, 3), sticky="w")

        self.webhook_var = ctk.StringVar(value=str(self.config.get("webhook_url", "")))
        ctk.CTkEntry(
            card,
            textvariable=self.webhook_var,
            corner_radius=8,
            fg_color="white",
            border_color=CARD_BORDER,
            border_width=1,
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=1, columnspan=2, padx=(4, 6), pady=(10, 3), sticky="we")

        # Row 1: User ID
        ctk.CTkLabel(
            card,
            text="Discord User ID",
            text_color=TEXT_PRIMARY,
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, padx=6, pady=3, sticky="w")

        self.user_var = ctk.StringVar(value=str(self.config.get("user_id", "")))
        ctk.CTkEntry(
            card,
            textvariable=self.user_var,
            corner_radius=8,
            fg_color="white",
            border_color=CARD_BORDER,
            border_width=1,
            text_color=TEXT_PRIMARY,
        ).grid(row=1, column=1, columnspan=2, padx=(4, 6), pady=3, sticky="we")

        # Row 2: Reference Image
        ctk.CTkLabel(
            card,
            text="Reference Image",
            text_color=TEXT_PRIMARY,
            font=("Segoe UI", 10),
        ).grid(row=2, column=0, padx=6, pady=3, sticky="w")

        self.ref_var = ctk.StringVar(
            value=str(self.config.get("reference_image_path", ""))
        )
        self.ref_entry = ctk.CTkEntry(
            card,
            textvariable=self.ref_var,
            corner_radius=8,
            fg_color="white",
            border_color=CARD_BORDER,
            border_width=1,
            text_color=TEXT_PRIMARY,
        )
        self.ref_entry.grid(row=2, column=1, padx=(4, 2), pady=3, sticky="we")

        self.ref_button = ctk.CTkButton(
            card,
            text="Add",
            width=40,
            height=24,
            corner_radius=12,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white",
            font=("Segoe UI", 11),
            command=self.on_browse_reference,
        )
        self.ref_button.grid(row=2, column=2, padx=(2, 6), pady=3, sticky="e")

        # Row 3: Buttons row
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=3, padx=6, pady=(4, 3), sticky="we")

        btn_frame.grid_columnconfigure(0, weight=0)
        btn_frame.grid_columnconfigure(1, weight=0)
        btn_frame.grid_columnconfigure(2, weight=0)
        btn_frame.grid_columnconfigure(3, weight=1)

        self.btn_discord = ctk.CTkButton(
            btn_frame,
            text="Discord",
            width=68,
            height=24,
            corner_radius=12,
            fg_color="white",
            hover_color="#e5e7eb",
            text_color=TEXT_PRIMARY,
            font=("Segoe UI", 10),
            command=self.on_open_discord,
        )
        self.btn_discord.grid(row=0, column=0, padx=(0, 3), sticky="w")

        self.btn_test = ctk.CTkButton(
            btn_frame,
            text="Test Connection",
            width=54,
            height=24,
            corner_radius=12,
            fg_color="white",
            hover_color="#e5e7eb",
            text_color=TEXT_PRIMARY,
            font=("Segoe UI", 10),
            command=self.on_test_discord,
        )
        self.btn_test.grid(row=0, column=1, padx=3, sticky="w")

        self.btn_save = ctk.CTkButton(
            btn_frame,
            text="Save Config",
            width=54,
            height=24,
            corner_radius=12,
            fg_color="white",
            hover_color="#e5e7eb",
            text_color=TEXT_PRIMARY,
            font=("Segoe UI", 10),
            command=self.on_save,
        )
        self.btn_save.grid(row=0, column=2, padx=3, sticky="w")

        self.watch_btn = ctk.CTkButton(
            btn_frame,
            text="Watch",
            width=70,
            height=24,
            corner_radius=12,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white",
            font=("Segoe UI", 10),
            command=self.on_toggle_watch,
        )
        self.watch_btn.grid(row=0, column=3, padx=(0, 0), sticky="e")

        # Row 4: Status + Version + Update (inline)
        status_frame = ctk.CTkFrame(card, fg_color="transparent")
        status_frame.grid(
            row=4, column=0, columnspan=3, padx=6, pady=(0, 2), sticky="we"
        )

        status_frame.grid_columnconfigure(0, weight=1)

        # Centered status text (less button-y)
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="● Stopped",
            font=("Segoe UI Semibold", 15),
            text_color=DANGER,
        )
        self.status_label.grid(row=0, column=0, columnspan=2, pady=(0, 2), sticky="n")

        # Bottom-right inline: Version + update status
        self.version_and_update = ctk.CTkLabel(
            status_frame,
            text=f"Version: {APP_VERSION}   •   Checking updates...",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 10),
        )
        self.version_and_update.grid(row=1, column=0, pady=(0, 2), sticky="s")

        # make it clickable
        self.version_and_update.bind("<Button-1>", self.on_update_click)


    # --------- Status label helpers ---------

    def _set_status(self, text: str, color: str) -> None:
        self.status_label.configure(
            text=text,
            text_color=color,
        )

    def _flash_detected_status(self) -> None:
        """Flash 'Detected!' for ~1.6s, then restore."""
        prev_text = self.status_label.cget("text")
        prev_color = self.status_label.cget("text_color")

        self._set_status("● Detected!", DETECTED)

        def restore():
            self._set_status(prev_text, prev_color)

        self.status_label.after(1600, restore)


    # --------- Config / validation -------

    def _update_config_from_ui(self) -> None:
        self.config["webhook_url"] = self.webhook_var.get().strip()
        self.config["user_id"] = self.user_var.get().strip()
        self.config["reference_image_path"] = self.ref_var.get().strip()


    # --------- Button handlers ---------

    def on_browse_reference(self) -> None:
        filename = filedialog.askopenfilename(
            title="Select reference image",
            filetypes=[
                ("Image files", "*.png;*.jpg;*.jpeg;*.bmp"),
                ("All files", "*.*"),
            ],
        )
        if filename:
            self.ref_var.set(filename)

    def on_save(self) -> None:
        self._update_config_from_ui()

        if not validate_discord_core(
            self.webhook_var.get(), self.user_var.get()
        ):
            return
        if not validate_reference_image(self.ref_var.get()):
            return

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

        if not validate_discord_core(webhook_url, user_id):
            return

        try:
            send_test_message(webhook_url, user_id, timeout=5.0)
            self._last_test_time = now
            messagebox.showinfo("Success", "Test message sent.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send test:\n{e}")

    def on_open_discord(self) -> None:
        webbrowser.open(DISCORD_SERVER_URL)

    def on_toggle_watch(self) -> None:
        if self._watcher is None or not self._watcher.is_running():
            self._start_watch()
        else:
            self._stop_watch()



    # --------- Watcher control ---------

    def _start_watch(self) -> None:
        self._update_config_from_ui()

        if not validate_discord_core(
            self.webhook_var.get(), self.user_var.get()
        ):
            return
        if not validate_reference_image(self.ref_var.get()):
            return

        save_config(self.config)

        messagebox.showinfo(
            "Mobile Discord Notifications",
            "If you would like Discord notifications to be directed to your phone "
            "INSTEAD of your PC, please 'Quit Discord' in your system tray.",
        )

        # Build watcher settings from config and start watcher
        settings = WatcherSettings.from_config(self.config)
        self._watcher = QPopWatcher(
            settings,
            on_detect=self._flash_detected_status,
        )
        self._watcher.start()

        self._set_status("● Watching", SUCCESS)
        self.watch_btn.configure(
            text="Watching",
            fg_color=SUCCESS,
            hover_color="#15803d",
        )

    def _stop_watch(self) -> None:
        if self._watcher:
            self._watcher.stop()

        self._set_status("● Stopped", DANGER)
        self.watch_btn.configure(
            text="Watch", fg_color=ACCENT, hover_color=ACCENT_HOVER
        )

    def _check_test_throttle(self):
        now = time.time()
        elapsed = now - self._last_test_time
        if elapsed < THROTTLE_SECONDS:
            return True, int(THROTTLE_SECONDS - elapsed), now
        return False, 0, now

    # --------- Updater logic ---------

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
                    "Update failed", clickable=False, color=DANGER
                ),
            )
            return

        self._update_info = info
        self.root.after(0, lambda: self._apply_update_info(info))

    def _apply_update_info(self, info: UpdateInfo) -> None:
        if info.available:
            self._set_update_status(
                "Update available", clickable=True, color=ACCENT
            )
        else:
            self._set_update_status(
                "Up to date", clickable=False, color=TEXT_MUTED
            )

    def _set_update_status(self, text: str, clickable: bool, color: str) -> None:
        self.version_and_update.configure(
            text=f"Version: {APP_VERSION}   •   {text}",
            text_color=color,
        )
        self._update_clickable = clickable
        self.version_and_update.configure(
            cursor="hand2" if clickable else "arrow"
        )

    def on_update_click(self, _event=None) -> None:
        """Handle clicking the update-status label."""
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

        self._set_update_status(
            "Downloading update...", clickable=False, color=ACCENT
        )
        threading.Thread(
            target=self._perform_update_install, daemon=True
        ).start()

    def _perform_update_install(self) -> None:
        try:
            assert self._update_info is not None
            self.update_manager.install_update(self._update_info)
        except Exception as exc:
            print("Update installation failed:", exc)
            self.root.after(
                0,
                lambda: self._set_update_status(
                    "Update failed – try again", clickable=True, color=DANGER
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

    # --------- Close / run ---------

    def on_close(self) -> None:
        if self._watcher:
            self._watcher.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()

