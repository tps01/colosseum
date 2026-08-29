"""Window icon helpers for the Colosseum GUI."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from typing import Any

_ASSETS = Path(__file__).resolve().parent / "assets"
_APP_USER_MODEL_ID = "Colosseum.GUI.1"


def init_windows_taskbar() -> None:
    """Prepare Windows taskbar identity and DPI handling before creating the window."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        if hasattr(ctypes.windll, "shcore"):
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        else:
            ctypes.windll.user32.SetProcessDPIAware()
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        return


def _apply_windows_native_icon(window: Any, icon_path: str) -> None:  # noqa: ANN401
    """Set title-bar and taskbar icons via Win32 (sharper than tk iconbitmap on high-DPI)."""
    import ctypes

    hwnd = window.winfo_id()
    try:
        dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
    except (AttributeError, OSError):
        dpi = 96
    scale = max(1, round(dpi / 96))
    image_icon = 1
    load_from_file = 0x0010
    wm_seticon = 0x0080
    icon_small, icon_big = 0, 1
    sizes = ((icon_small, min(64, 16 * scale)), (icon_big, min(256, 32 * scale)))
    for icon_type, size in sizes:
        handle = ctypes.windll.user32.LoadImageW(
            None,
            icon_path,
            image_icon,
            size,
            size,
            load_from_file,
        )
        if handle:
            ctypes.windll.user32.SendMessageW(hwnd, wm_seticon, icon_type, handle)


def apply_window_icon(window: Any) -> None:  # noqa: ANN401
    """Set title-bar and taskbar icons when bundled assets are available."""
    ico = _ASSETS / "colosseum.ico"
    try:
        if sys.platform == "win32" and ico.is_file():
            icon_path = str(ico.resolve())

            def _finalize_icon() -> None:
                window.iconbitmap(default=icon_path)
                _apply_windows_native_icon(window, icon_path)

            window.after_idle(_finalize_icon)
            return
        png = _ASSETS / "colosseum-512.png"
        if png.is_file():
            photo = tk.PhotoImage(file=str(png))
            window.iconphoto(True, photo)
            window._colosseum_icon = photo  # noqa: SLF001 — keep reference alive
    except tk.TclError:
        return
