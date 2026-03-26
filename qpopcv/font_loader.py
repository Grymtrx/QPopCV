"""
Load bundled TrueType fonts into the process font table using the Windows GDI API.

Fonts registered with FR_PRIVATE are available only to this process and are
automatically removed when the process exits — no system-wide side effects.
"""
import ctypes
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_FR_PRIVATE = 0x10  # Font is private to this process


def load_bundled_fonts(fonts_dir: Path) -> None:
    """Load all .ttf files in *fonts_dir* into the Windows font table."""
    if not fonts_dir.exists():
        logger.warning("Fonts directory not found: %s", fonts_dir)
        return

    loaded = 0
    for ttf in sorted(fonts_dir.glob("*.ttf")):
        result = ctypes.windll.gdi32.AddFontResourceExW(str(ttf), _FR_PRIVATE, 0)
        if result == 0:
            logger.warning("Failed to load font: %s", ttf.name)
        else:
            logger.debug("Loaded bundled font: %s", ttf.name)
            loaded += 1

    if loaded:
        logger.info("Loaded %d bundled font(s) from %s", loaded, fonts_dir)
