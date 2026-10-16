"""Loading map pictures for the overlay, and the Win32 constants the overlay windows share.

The overlay windows themselves: overlay_win32.Win32Overlay (Windows), overlay_qt.QtOverlay (fallback)."""
from __future__ import annotations

import ctypes
import sys

from PIL import Image, ImageSequence

from .mapimage import rotate_frames

IS_WIN = sys.platform == "win32"
BACKDROP = (18, 18, 20)         # behind half-transparent picture edges

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008

if IS_WIN:
    from ctypes import wintypes
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        _GetLong = _user32.GetWindowLongPtrW
        _SetLong = _user32.SetWindowLongPtrW
    else:  # pragma: no cover - 32-bit Python
        _GetLong = _user32.GetWindowLongW
        _SetLong = _user32.SetWindowLongW
    _GetLong.argtypes = [wintypes.HWND, ctypes.c_int]
    _GetLong.restype = ctypes.c_ssize_t
    _SetLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    _SetLong.restype = ctypes.c_ssize_t
    _user32.GetParent.argtypes = [wintypes.HWND]
    _user32.GetParent.restype = wintypes.HWND
    _user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, wintypes.UINT]
    _user32.SetWindowPos.restype = wintypes.BOOL
    HWND_TOPMOST = wintypes.HWND(-1)
    HWND_NOTOPMOST = wintypes.HWND(-2)
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x1, 0x2, 0x10, 0x20


MAX_LOAD_H = 1440          # the overlay is never taller than the screen (0.9 × 1440): bigger pictures shrink on load


def _fit(img: Image.Image) -> Image.Image:
    if img.height <= MAX_LOAD_H:
        return img
    # BOX: fast and clean for this step; the overlay scales down again with LANCZOS anyway
    return img.resize((max(1, round(img.width * MAX_LOAD_H / img.height)), MAX_LOAD_H), Image.BOX)


def load_frames(path: str, rotation: int = 0):
    """[(PIL RGBA image, duration ms)] – several for animated GIFs; ``rotation``: map turned clockwise (°).
    Pictures taller than MAX_LOAD_H are scaled down (Midwich: 6 × 2000² px = 96 MB otherwise)."""
    im = Image.open(path)
    frames = []
    if getattr(im, "is_animated", False):
        for fr in ImageSequence.Iterator(im):
            pic = fr.convert("RGBA")              # first: an animated WebP knows a frame's duration only once loaded
            d = fr.info.get("duration", 100) or 100
            frames.append((_fit(pic), max(40, int(d))))
    else:
        frames.append((_fit(im.convert("RGBA")), 0))
    return rotate_frames(frames, rotation)
