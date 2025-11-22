"""
QPopCV — World of Warcraft queue pop computer-vision discord notifier.

This package contains:
- The CustomTkinter UI (`QPopApp`)
- The queue watcher (`QPopWatcher`)
- The updater manager
- Helpers for Discord, validation, and theme
"""

from .app_ui import QPopApp
from .config import APP_VERSION

__all__ = ["QPopApp", "APP_VERSION"]
__version__ = APP_VERSION
__author__ = "Grymtrx"
__package_name__ = "QPopCV"


def main() -> None:
    #Entry point for the `qpopcv` console script.
    app = QPopApp()
    app.run()