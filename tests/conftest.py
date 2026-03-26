"""
Global pytest configuration for QPopCV tests.

Stubs out tkinter and its sub-modules before any application code is imported,
so all tests run headless (no display required, no Tkinter window).
"""
import sys
from unittest.mock import MagicMock


def _stub_tkinter():
    """Insert MagicMock stubs for tkinter into sys.modules."""
    tk_mock = MagicMock()
    messagebox_mock = MagicMock()

    sys.modules.setdefault("tkinter", tk_mock)
    sys.modules.setdefault("tkinter.messagebox", messagebox_mock)
    sys.modules.setdefault("tkinter.filedialog", MagicMock())
    sys.modules.setdefault("tkinter.ttk", MagicMock())
    sys.modules.setdefault("customtkinter", MagicMock())


_stub_tkinter()
