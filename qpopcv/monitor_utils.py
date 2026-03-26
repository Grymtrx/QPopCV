"""
Monitor enumeration for multi-monitor support (Windows only).

Uses ctypes to call Win32 EnumDisplayMonitors + GetMonitorInfoW.
Falls back to pyautogui.size() if enumeration fails.
"""
import ctypes
from ctypes import wintypes
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

MONITORINFOF_PRIMARY = 0x00000001


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def get_monitors() -> List[Dict]:
    """
    Return a list of monitor dicts, primary monitor first.

    Each dict has keys: x, y, w, h, is_primary.
    Falls back to a single pyautogui-based entry if Win32 enumeration fails.
    """
    monitors: List[Dict] = []

    try:
        MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_ulong,   # HMONITOR
            ctypes.c_ulong,   # HDC
            ctypes.POINTER(wintypes.RECT),
            ctypes.c_long,    # LPARAM
        )

        def _callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            info = _MONITORINFO()
            info.cbSize = ctypes.sizeof(_MONITORINFO)
            ctypes.windll.user32.GetMonitorInfoW(hMonitor, ctypes.byref(info))
            r = info.rcMonitor
            monitors.append({
                "x": r.left,
                "y": r.top,
                "w": r.right - r.left,
                "h": r.bottom - r.top,
                "is_primary": bool(info.dwFlags & MONITORINFOF_PRIMARY),
            })
            return True

        ctypes.windll.user32.EnumDisplayMonitors(
            None, None, MonitorEnumProc(_callback), 0
        )

        if monitors:
            # Primary first, then others sorted left-to-right, top-to-bottom
            monitors.sort(key=lambda m: (not m["is_primary"], m["x"], m["y"]))
            return monitors

    except Exception as exc:
        logger.warning("Monitor enumeration failed, falling back to pyautogui: %s", exc)

    # Fallback
    import pyautogui
    w, h = pyautogui.size()
    return [{"x": 0, "y": 0, "w": w, "h": h, "is_primary": True}]


def compute_top_center_region(monitor: Dict) -> Tuple[int, int, int, int]:
    """Return the top-center third of a monitor as (x, y, w, h)."""
    x = monitor["x"] + monitor["w"] // 3
    y = monitor["y"]
    w = monitor["w"] // 3
    h = monitor["h"] // 2
    return x, y, w, h
