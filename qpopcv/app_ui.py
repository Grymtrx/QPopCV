from typing import Dict, List, Optional, Tuple
import threading
import time
import webbrowser
from pathlib import Path
import logging

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
from .watcher import QPopWatcher, WatcherSettings

TEST_THROTTLE_SECONDS = 1
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
from .validators import validate_discord_core, validate_reference_images
from .monitor_utils import get_monitors
from .discord_client import send_test_message

logger = logging.getLogger(__name__)

class QPopApp:
    def __init__(self) -> None:
        self.config: Dict[str, object] = load_config()
        self._last_test_time: float = 0.0
        self._watcher: Optional[QPopWatcher] = None
        self._update_info: Optional[UpdateInfo] = None
        self._update_clickable: bool = False

        monitors = get_monitors()
        self._monitor_labels = []
        for i, m in enumerate(monitors):
            label = f"Monitor {i + 1}"
            if m["is_primary"]:
                label += " \u2013 Primary"
            self._monitor_labels.append(label)

        # Reference image rows: list of (frame, StringVar, browse_btn, remove_btn)
        self._ref_rows: List[Tuple] = []

        self.update_manager = UpdateManager(
            current_version=APP_VERSION, app_dir=APP_DIR
        )

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        # Window title
        self.root.title("QPopCV Watcher App")
        self.root.geometry("360x280")
        self.root.minsize(360, 280)
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

        # Row 2: Reference Images (dynamic sub-frame)
        ctk.CTkLabel(
            card,
            text="Ref Images",
            text_color=TEXT_PRIMARY,
            font=("Segoe UI", 10),
        ).grid(row=2, column=0, padx=6, pady=3, sticky="nw")

        ref_section = ctk.CTkFrame(card, fg_color="transparent")
        ref_section.grid(row=2, column=1, columnspan=2, padx=(4, 6), pady=0, sticky="we")
        ref_section.grid_columnconfigure(0, weight=1)
        ref_section.grid_columnconfigure(1, weight=0)
        ref_section.grid_columnconfigure(2, weight=0)
        self._ref_section = ref_section

        # Add button (placed dynamically by _refresh_add_btn_position)
        self._add_ref_btn = ctk.CTkButton(
            ref_section,
            text="+ Add Image",
            width=90,
            height=20,
            corner_radius=10,
            fg_color="white",
            hover_color="#e5e7eb",
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=CARD_BORDER,
            font=("Segoe UI", 9),
            command=self._add_ref_row,
        )

        # Populate from config
        saved_paths: list = self.config.get("reference_image_paths", [])  # type: ignore[assignment]
        if not saved_paths:
            saved_paths = [""]
        for p in saved_paths:
            self._add_ref_row(str(p))
        self._refresh_add_btn_position()

        # Row 3: Game Monitor
        ctk.CTkLabel(
            card,
            text="Game Monitor",
            text_color=TEXT_PRIMARY,
            font=("Segoe UI", 10),
        ).grid(row=3, column=0, padx=6, pady=3, sticky="w")

        saved_idx = int(str(self.config.get("monitor_index", 0)))
        saved_idx = max(0, min(saved_idx, len(self._monitor_labels) - 1))
        self.monitor_var = ctk.StringVar(value=self._monitor_labels[saved_idx])
        ctk.CTkOptionMenu(
            card,
            variable=self.monitor_var,
            values=self._monitor_labels,
            corner_radius=8,
            fg_color="white",
            button_color=CARD_BORDER,
            button_hover_color=ACCENT_HOVER,
            text_color=TEXT_PRIMARY,
            dropdown_fg_color="white",
            dropdown_text_color=TEXT_PRIMARY,
            dropdown_hover_color="#e5e7eb",
            font=("Segoe UI", 10),
        ).grid(row=3, column=1, columnspan=2, padx=(4, 6), pady=3, sticky="we")

        # Row 4: Buttons row
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=4, column=0, columnspan=3, padx=6, pady=(4, 3), sticky="we")

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

        # Row 5: Status + Version + Update (inline)
        status_frame = ctk.CTkFrame(card, fg_color="transparent")
        status_frame.grid(
            row=5, column=0, columnspan=3, padx=6, pady=(0, 2), sticky="we"
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


    # --------- Reference image row management ---------

    MAX_REF_IMAGES = 5

    def _add_ref_row(self, path: str = "") -> None:
        if len(self._ref_rows) >= self.MAX_REF_IMAGES:
            return
        idx = len(self._ref_rows)
        var = ctk.StringVar(value=path)

        row_frame = ctk.CTkFrame(self._ref_section, fg_color="transparent")
        row_frame.grid(row=idx, column=0, columnspan=3, padx=0, pady=1, sticky="we")
        row_frame.grid_columnconfigure(0, weight=1)
        row_frame.grid_columnconfigure(1, weight=0)
        row_frame.grid_columnconfigure(2, weight=0)

        entry = ctk.CTkEntry(
            row_frame,
            textvariable=var,
            corner_radius=8,
            fg_color="white",
            border_color=CARD_BORDER,
            border_width=1,
            text_color=TEXT_PRIMARY,
        )
        entry.grid(row=0, column=0, padx=(0, 2), pady=0, sticky="we")

        browse_btn = ctk.CTkButton(
            row_frame,
            text="...",
            width=28,
            height=24,
            corner_radius=8,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white",
            font=("Segoe UI", 11),
            command=lambda v=var: self._browse_reference(v),
        )
        browse_btn.grid(row=0, column=1, padx=(0, 2), pady=0)

        remove_btn = ctk.CTkButton(
            row_frame,
            text="×",
            width=24,
            height=24,
            corner_radius=8,
            fg_color="#e5e7eb",
            hover_color=DANGER,
            text_color=TEXT_PRIMARY,
            font=("Segoe UI", 12),
            command=lambda i=idx: self._remove_ref_row(i),
        )
        remove_btn.grid(row=0, column=2, padx=(0, 6), pady=0)

        self._ref_rows.append((row_frame, var, browse_btn, remove_btn))
        self._refresh_remove_btns()
        self._refresh_add_btn_position()

    def _remove_ref_row(self, idx: int) -> None:
        if len(self._ref_rows) <= 1:
            return  # always keep at least 1
        row_frame, _, _, _ = self._ref_rows.pop(idx)
        row_frame.destroy()

        # Re-grid remaining rows at correct indices
        for i, (frame, _, _, _) in enumerate(self._ref_rows):
            frame.grid(row=i, column=0, columnspan=3, padx=0, pady=1, sticky="we")

        # Rebind remove buttons with updated indices
        for i, (_, _, _, remove_btn) in enumerate(self._ref_rows):
            remove_btn.configure(command=lambda i=i: self._remove_ref_row(i))

        self._refresh_remove_btns()
        self._refresh_add_btn_position()

    def _refresh_remove_btns(self) -> None:
        """Disable remove button when only 1 row remains."""
        only_one = len(self._ref_rows) == 1
        for _, _, _, remove_btn in self._ref_rows:
            remove_btn.configure(state="disabled" if only_one else "normal")

    def _refresh_add_btn_position(self) -> None:
        if len(self._ref_rows) < self.MAX_REF_IMAGES:
            self._add_ref_btn.grid(
                row=len(self._ref_rows), column=0, columnspan=3,
                padx=0, pady=(1, 3), sticky="w",
            )
        else:
            self._add_ref_btn.grid_remove()

    # --------- Config / validation -------

    def _get_ref_paths(self) -> List[str]:
        return [var.get().strip() for _, var, _, _ in self._ref_rows]

    def _update_config_from_ui(self) -> None:
        self.config["webhook_url"] = self.webhook_var.get().strip()
        self.config["user_id"] = self.user_var.get().strip()
        self.config["reference_image_paths"] = [p for p in self._get_ref_paths() if p]
        selected = self.monitor_var.get()
        idx = self._monitor_labels.index(selected) if selected in self._monitor_labels else 0
        self.config["monitor_index"] = idx


    # --------- Button handlers ---------

    def _browse_reference(self, var: ctk.StringVar) -> None:
        filename = filedialog.askopenfilename(
            title="Select reference image",
            filetypes=[
                ("Image files", "*.png;*.jpg;*.jpeg;*.bmp"),
                ("All files", "*.*"),
            ],
        )
        if filename:
            var.set(filename)

    def on_save(self) -> None:
        self._update_config_from_ui()

        if not validate_discord_core(
            self.webhook_var.get(), self.user_var.get()
        ):
            return
        if not validate_reference_images(self._get_ref_paths()):
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
        if not validate_reference_images(self._get_ref_paths()):
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
        if elapsed < TEST_THROTTLE_SECONDS:
            return True, int(TEST_THROTTLE_SECONDS - elapsed), now
        return False, 0, now

    # --------- Updater logic ---------

    def _start_update_check(self) -> None:
        """Start a background update check after UI has loaded."""

        def worker() -> None:
            try:
                # NOTE: correct name is check_for_update (no 's')
                info = self.update_manager.check_for_update()
                self._update_info = info
                # Apply result on the Tk thread
                self.root.after(0, lambda: self._apply_update_info(info))
            except Exception as exc:
                logger.exception("Update check failed: %s", exc)
                # If the check fails (no internet, GitHub issue, etc.),
                # just show "Up to date" instead of a scary error.
                self.root.after(
                    0,
                    lambda: self._set_update_status(
                        "Up to date", clickable=False, color=TEXT_MUTED
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _apply_update_info(self, info: UpdateInfo) -> None:
        """Update the status label based on UpdateInfo result."""
        if info.available and info.download_url:
            text = f"Update available: {info.latest_version}"
            self._set_update_status(text, clickable=True, color=ACCENT)
        else:
            self._set_update_status("Up to date", clickable=False, color=TEXT_MUTED)

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
            # Not clickable => either up to date or check failed quietly
            messagebox.showinfo("QPopCV", "You are running the latest version.")
            return

        if not self._update_info or not self._update_info.available:
            messagebox.showinfo("QPopCV", "No update is currently available.")
            return

        if not messagebox.askyesno(
            "Update Available",
            (
                f"Version {self._update_info.latest_version} is available.\n"
                "Would you like to download and install it now?"
            ),
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
            logger.exception("Update installation failed: %s", exc)

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

        # Installation kicked off successfully (external updater for frozen exe)
        self.root.after(0, self._restart_after_update)

    def _restart_after_update(self) -> None:
        import os
        messagebox.showinfo(
            "Update Installed",
            "The newest version has been installed. QPopCV will now close "
            "to finish the update.",
        )
        self.on_close()
        os._exit(0)


    # --------- Close / run ---------

    def on_close(self) -> None:
        if self._watcher:
            self._watcher.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()