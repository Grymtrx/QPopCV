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
    FONTS_DIR,
    load_config,
    save_config,
)
from .font_loader import load_bundled_fonts
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
    TEXT_SECTION,
    DANGER,
    SUCCESS,
    DETECTED,
    STATUS_IDLE,
    DISCORD_BLURPLE,
    DISCORD_BLURPLE_HOVER,
    PILL_IDLE_BG,
    PILL_IDLE_BORDER,
    PILL_RUNNING_BG,
    PILL_RUNNING_BORDER,
    PILL_DETECTED_BG,
    PILL_DETECTED_BORDER,
)
from .validators import validate_discord_core, validate_reference_images
from .monitor_utils import get_monitors
from .discord_client import send_test_message

logger = logging.getLogger(__name__)

class QPopApp:
    def __init__(self) -> None:
        load_bundled_fonts(FONTS_DIR)
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
        self.root.title("QPopCV")
        self.root.geometry("480x280")
        self.root.minsize(480, 200)
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
            corner_radius=8,
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
        )
        card.grid(row=0, column=0, padx=12, pady=10, sticky="new")

        card.grid_columnconfigure(0, weight=0, minsize=90)
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(2, weight=0)

        # ── DISCORD section ───────────────────────────────────────────────
        discord_hdr = ctk.CTkFrame(card, fg_color="transparent")
        discord_hdr.grid(row=0, column=0, columnspan=3, padx=10, pady=(12, 2), sticky="we")
        discord_hdr.grid_columnconfigure(0, weight=1)
        discord_hdr.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            discord_hdr, text="Discord",
            text_color=TEXT_SECTION,
            font=("Inter", 11, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self.btn_test = ctk.CTkButton(
            discord_hdr,
            text="Test",
            width=54, height=22,
            corner_radius=6,
            fg_color="transparent",
            hover_color="#e5e7eb",
            text_color=TEXT_MUTED,
            border_width=1,
            border_color=CARD_BORDER,
            font=("Inter", 9),
            command=self.on_test_discord,
        )
        self.btn_test.grid(row=0, column=1, sticky="e")

        # Row 1: Webhook
        ctk.CTkLabel(
            card, text="Webhook",
            text_color=TEXT_PRIMARY,
            font=("Inter", 10),
        ).grid(row=1, column=0, padx=(10, 4), pady=3, sticky="w")

        self.webhook_var = ctk.StringVar(value=str(self.config.get("webhook_url", "")))
        ctk.CTkEntry(
            card, textvariable=self.webhook_var,
            corner_radius=5, fg_color="white",
            border_color=CARD_BORDER, border_width=1,
            text_color=TEXT_PRIMARY,
        ).grid(row=1, column=1, columnspan=2, padx=(0, 10), pady=3, sticky="we")

        # Row 2: User ID
        ctk.CTkLabel(
            card, text="User ID",
            text_color=TEXT_PRIMARY,
            font=("Inter", 10),
        ).grid(row=2, column=0, padx=(10, 4), pady=(3, 6), sticky="w")

        self.user_var = ctk.StringVar(value=str(self.config.get("user_id", "")))
        ctk.CTkEntry(
            card, textvariable=self.user_var,
            corner_radius=5, fg_color="white",
            border_color=CARD_BORDER, border_width=1,
            text_color=TEXT_PRIMARY,
        ).grid(row=2, column=1, columnspan=2, padx=(0, 10), pady=(3, 6), sticky="we")

        # Row 3: Separator
        ctk.CTkFrame(
            card, height=1, fg_color=CARD_BORDER, corner_radius=0,
        ).grid(row=3, column=0, columnspan=3, padx=10, pady=0, sticky="we")

        # ── DETECTION section ─────────────────────────────────────────────
        ctk.CTkLabel(
            card, text="Detection",
            text_color=TEXT_SECTION,
            font=("Inter", 11, "bold"),
        ).grid(row=4, column=0, columnspan=3, padx=10, pady=(10, 2), sticky="w")

        # Row 5: Game Monitor
        ctk.CTkLabel(
            card, text="Game Monitor",
            text_color=TEXT_PRIMARY,
            font=("Inter", 10),
        ).grid(row=5, column=0, padx=(10, 4), pady=3, sticky="w")

        saved_idx = int(str(self.config.get("monitor_index", 0)))
        saved_idx = max(0, min(saved_idx, len(self._monitor_labels) - 1))
        self.monitor_var = ctk.StringVar(value=self._monitor_labels[saved_idx])
        ctk.CTkComboBox(
            card, variable=self.monitor_var, values=self._monitor_labels,
            corner_radius=5, fg_color="white",
            border_color=CARD_BORDER, border_width=1,
            button_color=CARD_BORDER, button_hover_color=ACCENT_HOVER,
            text_color=TEXT_PRIMARY, dropdown_fg_color="white",
            dropdown_text_color=TEXT_PRIMARY, dropdown_hover_color="#e5e7eb",
            font=("Inter", 10), state="readonly",
        ).grid(row=5, column=1, columnspan=2, padx=(0, 10), pady=3, sticky="we")

        # Row 6: Ref Images
        ctk.CTkLabel(
            card, text="Ref Images",
            text_color=TEXT_PRIMARY,
            font=("Inter", 10),
        ).grid(row=6, column=0, padx=(10, 4), pady=3, sticky="nw")

        ref_section = ctk.CTkFrame(card, fg_color="transparent")
        ref_section.grid(row=6, column=1, columnspan=2, padx=(0, 10), pady=0, sticky="we")
        ref_section.grid_columnconfigure(0, weight=1)
        ref_section.grid_columnconfigure(1, weight=0)
        ref_section.grid_columnconfigure(2, weight=0)
        self._ref_section = ref_section

        # Add button (placed dynamically by _refresh_add_btn_position)
        self._add_ref_btn = ctk.CTkButton(
            ref_section,
            text="+ Add Image",
            width=90, height=26,
            corner_radius=5,
            fg_color="transparent",
            hover_color="#e5e7eb",
            text_color=TEXT_MUTED,
            border_width=1,
            border_color=CARD_BORDER,
            font=("Inter", 9),
            command=self._add_ref_row,
        )

        # Populate from config
        saved_paths: list = self.config.get("reference_image_paths", [])  # type: ignore[assignment]
        if not saved_paths:
            saved_paths = [""]
        for p in saved_paths:
            self._add_ref_row(str(p))
        self._refresh_add_btn_position()
        self.root.after(0, self._fit_window)

        # ── Action buttons ────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=7, column=0, columnspan=3, padx=10, pady=(10, 4), sticky="we")

        btn_frame.grid_columnconfigure(0, weight=0)  # Save
        btn_frame.grid_columnconfigure(1, weight=1)  # status pill (center)
        btn_frame.grid_columnconfigure(2, weight=0)  # Watch

        # Save — outlined secondary (left)
        self.btn_save = ctk.CTkButton(
            btn_frame,
            text="Save Configuration",
            width=148, height=32,
            corner_radius=6,
            fg_color="transparent",
            hover_color="#e5e7eb",
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=CARD_BORDER,
            font=("Inter", 10),
            command=self.on_save,
        )
        self.btn_save.grid(row=0, column=0, sticky="w")

        # Status pill — centered between Save and Watch
        pill_holder = ctk.CTkFrame(btn_frame, fg_color="transparent")
        pill_holder.grid(row=0, column=1, sticky="nswe")
        pill_holder.grid_columnconfigure(0, weight=1)
        pill_holder.grid_columnconfigure(1, weight=0)
        pill_holder.grid_columnconfigure(2, weight=1)

        self._status_pill_frame = ctk.CTkFrame(
            pill_holder,
            corner_radius=8,
            fg_color=PILL_IDLE_BG,
            border_width=1,
            border_color=PILL_IDLE_BORDER,
        )
        self._status_pill_frame.grid(row=0, column=1, pady=2)

        self.status_label = ctk.CTkLabel(
            self._status_pill_frame,
            text="● Stopped",
            font=("Inter", 12, "bold"),
            text_color=STATUS_IDLE,
        )
        self.status_label.grid(padx=22, pady=5)

        # Watch — primary CTA (right)
        self.watch_btn = ctk.CTkButton(
            btn_frame,
            text="▶  Watch",
            width=96, height=32,
            corner_radius=6,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white",
            font=("Inter", 10, "bold"),
            command=self.on_toggle_watch,
        )
        self.watch_btn.grid(row=0, column=2, sticky="e")

        # ── Footer: Join Discord + mobile hint + version ──────────────────
        footer_frame = ctk.CTkFrame(card, fg_color="transparent")
        footer_frame.grid(row=8, column=0, columnspan=3, padx=10, pady=(2, 10), sticky="we")
        footer_frame.grid_columnconfigure(0, weight=0)
        footer_frame.grid_columnconfigure(1, weight=1)
        footer_frame.grid_columnconfigure(2, weight=0)

        # Join Discord — community/support link (blurple, prominent)
        self.btn_discord = ctk.CTkButton(
            footer_frame,
            text="Join Discord",
            width=88, height=22,
            corner_radius=6,
            fg_color="transparent",
            hover_color=DISCORD_BLURPLE_HOVER,
            text_color=DISCORD_BLURPLE,
            font=("Inter", 9, "bold"),
            command=self.on_open_discord,
        )
        self.btn_discord.grid(row=0, column=0, sticky="w")

        # Mobile hint — centered, small
        ctk.CTkLabel(
            footer_frame,
            text="Quit Discord in system tray for mobile notifications",
            text_color=TEXT_MUTED,
            font=("Inter", 9),
        ).grid(row=0, column=1, padx=4, sticky="w")

        # Version + update status (right-aligned, clickable)
        self.version_and_update = ctk.CTkLabel(
            footer_frame,
            text=f"v{APP_VERSION} · Checking...",
            text_color=TEXT_MUTED,
            font=("Inter", 9),
        )
        self.version_and_update.grid(row=0, column=2, sticky="e")
        self.version_and_update.bind("<Button-1>", self.on_update_click)



    def _fit_window(self) -> None:
        self.root.update_idletasks()
        self.root.geometry(f"480x{self.root.winfo_reqheight()}")

    # --------- Status label helpers ---------

    def _set_status(self, text: str, color: str) -> None:
        # Map status color to appropriate pill background
        if color == DETECTED:
            pill_bg, pill_border = PILL_DETECTED_BG, PILL_DETECTED_BORDER
        elif color == SUCCESS and text.startswith("●"):
            pill_bg, pill_border = PILL_RUNNING_BG, PILL_RUNNING_BORDER
        else:
            pill_bg, pill_border = PILL_IDLE_BG, PILL_IDLE_BORDER
        self.status_label.configure(text=text, text_color=color)
        self._status_pill_frame.configure(fg_color=pill_bg, border_color=pill_border)

    def _flash_detected_status(self) -> None:
        """Flash 'Detected!' for ~1.6s, then restore."""
        prev_text = self.status_label.cget("text")
        prev_color = self.status_label.cget("text_color")

        self._set_status("● Detected!", DETECTED)

        def restore():
            self._set_status(prev_text, prev_color)

        self.status_label.after(1600, restore)

    def _flash_status(self, text: str, color: str, duration_ms: int = 2000) -> None:
        """Temporarily show a status message, then restore the previous state."""
        prev_text = self.status_label.cget("text")
        prev_color = self.status_label.cget("text_color")

        self._set_status(text, color)

        def restore():
            self._set_status(prev_text, prev_color)

        self.status_label.after(duration_ms, restore)


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
            corner_radius=5,
            fg_color="white",
            border_color=CARD_BORDER,
            border_width=1,
            text_color=TEXT_PRIMARY,
        )
        entry.grid(row=0, column=0, padx=(0, 2), pady=0, sticky="we")

        browse_btn = ctk.CTkButton(
            row_frame,
            text="...",
            width=32,
            height=26,
            corner_radius=5,
            fg_color="white",
            hover_color="#e5e7eb",
            text_color=TEXT_MUTED,
            border_width=1,
            border_color=CARD_BORDER,
            font=("Inter", 10),
            command=lambda v=var: self._browse_reference(v),
        )
        browse_btn.grid(row=0, column=1, padx=(0, 2), pady=1)

        remove_btn = ctk.CTkButton(
            row_frame,
            text="✕",
            width=26,
            height=26,
            corner_radius=5,
            fg_color="transparent",
            hover_color="#fee2e2",
            text_color=TEXT_MUTED,
            font=("Inter", 11),
            command=lambda i=idx: self._remove_ref_row(i),
        )
        remove_btn.grid(row=0, column=2, padx=(0, 2), pady=1)

        self._ref_rows.append((row_frame, var, browse_btn, remove_btn))
        self._refresh_remove_btns()
        self._refresh_add_btn_position()
        self.root.after(0, self._fit_window)

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
        self.root.after(0, self._fit_window)

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
        self._flash_status("✓ Saved", SUCCESS, duration_ms=2000)

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

        # Build watcher settings from config and start watcher
        settings = WatcherSettings.from_config(self.config)
        self._watcher = QPopWatcher(
            settings,
            on_detect=self._flash_detected_status,
        )
        self._watcher.start()

        if self._watcher.oversized_refs:
            names = "\n".join(f"  • {p.name}" for p in self._watcher.oversized_refs)
            rw, rh = self._watcher._region[2], self._watcher._region[3]
            messagebox.showwarning(
                "Reference Image Too Large",
                f"The following image(s) are larger than the detection zone ({rw}×{rh}px) "
                f"and will be ignored:\n\n{names}\n\n"
                "Take a cropped screenshot of just the queue popup dialog, not the full screen.",
            )

        self._set_status("● Watching", SUCCESS)
        self.watch_btn.configure(
            text="■  Stop",
            fg_color=SUCCESS,
            hover_color="#15803d",
            font=("Inter", 10, "bold"),
        )

    def _stop_watch(self) -> None:
        if self._watcher:
            self._watcher.stop()

        self._set_status("● Stopped", STATUS_IDLE)
        self.watch_btn.configure(
            text="▶  Watch",
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            font=("Inter", 10, "bold"),
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
            text=f"v{APP_VERSION} · {text}",
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