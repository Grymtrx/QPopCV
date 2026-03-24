# conftest.py — repo root.
#
# Stubs out tkinter, pyautogui, and customtkinter before any test module
# is imported. This lets us test qpopcv submodules headlessly without a
# display, Tk root, or screen access.

import sys
import types
from unittest.mock import MagicMock


def _stub_tkinter():
    tk = types.ModuleType("tkinter")
    # pymsgbox checks tk.TkVersion at import time
    tk.TkVersion = 8.6
    tk.StringVar = MagicMock()

    filedialog_mod = types.ModuleType("tkinter.filedialog")
    filedialog_mod.askopenfilename = MagicMock(return_value="")

    messagebox_mod = types.ModuleType("tkinter.messagebox")
    messagebox_mod.showwarning = MagicMock(return_value=None)
    messagebox_mod.showinfo = MagicMock(return_value=None)
    messagebox_mod.showerror = MagicMock(return_value=None)
    messagebox_mod.askyesno = MagicMock(return_value=False)

    tk.filedialog = filedialog_mod
    tk.messagebox = messagebox_mod

    sys.modules.setdefault("tkinter", tk)
    sys.modules.setdefault("tkinter.filedialog", filedialog_mod)
    sys.modules.setdefault("tkinter.messagebox", messagebox_mod)


def _stub_pyautogui():
    pag = MagicMock()
    pag.size = MagicMock(return_value=(1920, 1080))
    pag.screenshot = MagicMock(return_value=MagicMock())
    pag.locate = MagicMock(return_value=None)
    pag.ImageNotFoundException = Exception

    # pymsgbox is pulled in by pyautogui — stub it too
    pymsgbox = MagicMock()
    pymsgbox.alert = MagicMock()
    pymsgbox.confirm = MagicMock()
    pymsgbox.prompt = MagicMock()
    pymsgbox.password = MagicMock()

    sys.modules.setdefault("pyautogui", pag)
    sys.modules.setdefault("pymsgbox", pymsgbox)


def _stub_customtkinter():
    ctk = MagicMock()
    ctk.CTk = MagicMock
    ctk.CTkFrame = MagicMock
    ctk.CTkLabel = MagicMock
    ctk.CTkEntry = MagicMock
    ctk.CTkButton = MagicMock
    ctk.StringVar = MagicMock
    sys.modules.setdefault("customtkinter", ctk)


_stub_tkinter()
_stub_pyautogui()
_stub_customtkinter()
