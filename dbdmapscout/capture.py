"""Finding the Dead by Daylight window and grabbing pixels from the screen.

Only the screen is read (like OBS or Discord screen sharing). The game process
is never opened, no input is sent, no game file is read.
"""
from __future__ import annotations

import ctypes
import glob
import os
import sys
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

IS_WIN = sys.platform == "win32"


# --------------------------------------------------------------------- Win32
if IS_WIN:
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.ClientToScreen.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetTopWindow.argtypes = [wintypes.HWND]
    user32.GetTopWindow.restype = wintypes.HWND
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    GA_ROOT = 2
    GW_HWNDNEXT = 2
    GW_HWNDPREV = 3
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT, WS_EX_LAYERED = 0x20, 0x80000

    # window manager only (no process access): outer edges as drawn by DWM, monitor work area
    dwmapi = ctypes.WinDLL("dwmapi")
    dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
    DWMWA_EXTENDED_FRAME_BOUNDS = 9
    DWMWA_CLOAKED = 14

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]

    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    MONITOR_DEFAULTTONEAREST = 2

    class CURSORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hCursor", wintypes.HANDLE),
                    ("ptScreenPos", wintypes.POINT)]

    user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
    user32.GetCursorInfo.restype = wintypes.BOOL


def enable_dpi_awareness():
    """Physical pixels everywhere (window rects, capture, overlay)."""
    if not IS_WIN:
        return
    try:
        f = ctypes.windll.user32.SetProcessDpiAwarenessContext
        f.argtypes = [ctypes.c_void_p]
        f.restype = ctypes.c_int
        if f(ctypes.c_void_p(-4)):          # PER_MONITOR_AWARE_V2
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def _window_text(hwnd) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _class_name(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


@dataclass
class GameWindow:
    hwnd: int
    title: str
    left: int
    top: int
    width: int
    height: int
    minimized: bool = False
    # left/top/width/height: the client area (the game picture)
    client: tuple | None = None          # client area (x, y, w, h) on screen
    outer: tuple | None = None           # window incl. title bar and frame, as DWM draws it
    window: tuple | None = None          # GetWindowRect (outer + invisible resize borders)
    monitor: tuple | None = None         # work area of the window's monitor (without taskbar)

    @property
    def rect(self):
        return self.left, self.top, self.width, self.height

    def capture_offset(self, size):
        """Position of the game picture inside a window-capture picture of ``size`` (WGC captures the
        whole window in window mode, title bar included), or None if the size fits no known frame."""
        if size is None:
            return None
        size = tuple(size)
        if self.client and size == tuple(self.client[2:]):
            frame = self.client                    # borderless: picture = client area
        else:
            frame = next((r for r in (self.outer, self.window) if r and size == tuple(r[2:])), None)
        if frame is None:
            return None
        return self.left - frame[0], self.top - frame[1]


def is_game_window(hwnd) -> bool:
    """Visible Unreal Engine window titled DeadByDaylight."""
    if not IS_WIN or not hwnd:
        return False
    try:
        return (bool(user32.IsWindowVisible(hwnd)) and _class_name(hwnd) == "UnrealWindow"
                and "deadbydaylight" in _window_text(hwnd).lower().replace(" ", ""))
    except Exception:
        return False


def _client_rect(hwnd):
    rc = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rc)):
        return None
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, rc.right - rc.left, rc.bottom - rc.top


def _outer_rect(hwnd):
    rc = wintypes.RECT()
    if dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rc), ctypes.sizeof(rc)) != 0:
        return None
    return rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top


def _monitor_work_area(hwnd):
    mon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not mon or not user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
        return None
    r = mi.rcWork
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def _window_rect(hwnd):
    rc = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rc)):
        return None
    return rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top


def window_geometry(hwnd):
    """(client, outer, window rect, monitor work area) of a window, each (x, y, w, h) or None."""
    if not IS_WIN:
        return None, None, None, None
    out = []
    for f in (_client_rect, _outer_rect, _window_rect, _monitor_work_area):
        try:
            out.append(f(hwnd))
        except Exception:
            out.append(None)
    return tuple(out)


def find_game_window() -> GameWindow | None:
    """The DBD window: Unreal Engine window class + title "DeadByDaylight".

    Only window-manager information is used (title, class, position). The game
    process itself is never opened. If several windows qualify, the one in the
    foreground wins, otherwise the biggest.
    """
    if not IS_WIN:
        return None
    hits = []

    def cb(hwnd, _):
        if is_game_window(hwnd):
            hits.append(int(hwnd))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    if not hits:
        return None
    fg = foreground_root()
    best, best_key = None, None
    for hwnd in hits:
        rect = _client_rect(hwnd)
        if rect is None:
            continue
        minimized = bool(user32.IsIconic(hwnd))
        key = (hwnd == fg, not minimized, rect[2] * rect[3])
        if best_key is None or key > best_key:
            best, best_key = (hwnd, rect, minimized), key
    if best is None:
        return None
    hwnd, client, minimized = best
    _client, outer, window, monitor = window_geometry(hwnd)
    x, y, w, h = client
    return GameWindow(hwnd=hwnd, title=_window_text(hwnd), left=x, top=y, width=w, height=h,
                      minimized=minimized, client=client, outer=outer, window=window, monitor=monitor)


def foreground_root() -> int:
    """Top-level window that currently has the focus (0 if none / not Windows)."""
    if not IS_WIN:
        return 0
    h = user32.GetForegroundWindow()
    if not h:
        return 0
    root = user32.GetAncestor(h, GA_ROOT)
    return int(root or h)


def cursor_state():
    """(visible, x, y) of the Windows mouse pointer, None if unknown.

    The same system information screen recorders use to draw the pointer
    (GetCursorInfo). Nothing is sent to or read from the game.
    """
    if not IS_WIN:
        return None
    try:
        ci = CURSORINFO()
        ci.cbSize = ctypes.sizeof(CURSORINFO)
        if not user32.GetCursorInfo(ctypes.byref(ci)):
            return None                      # e.g. secure desktop (UAC prompt)
        visible = bool(ci.flags & 0x1) and not (ci.flags & 0x2) and bool(ci.hCursor)
        return visible, int(ci.ptScreenPos.x), int(ci.ptScreenPos.y)
    except Exception:
        return None


def describe_window(hwnd) -> str:
    if not IS_WIN or not hwnd:
        return "(keins)"
    try:
        return f"„{_window_text(hwnd)[:40]}“ [{_class_name(hwnd)}]"
    except Exception:
        return "(unbekannt)"


def is_above(upper, lower) -> bool:
    """True if window `upper` is above window `lower` in the Z order."""
    if not IS_WIN or not upper or not lower:
        return False
    h = user32.GetTopWindow(None)
    steps = 0
    while h and steps < 5000:
        h = int(h)
        if h == int(upper):
            return True
        if h == int(lower):
            return False
        h = user32.GetWindow(h, GW_HWNDNEXT)
        steps += 1
    return False


# Never hide DBD's picture: the taskbar is a strip at the screen edge (shown over a full-screen DBD in the
# background); click-through overlays (ours, GPU overlays) are left out by their style.
NOT_COVERING = ("Shell_TrayWnd", "Shell_SecondaryTrayWnd")


def _cloaked(hwnd) -> bool:
    """"Visible" but not drawn by DWM (other virtual desktop, suspended store app)."""
    v = ctypes.c_int(0)
    return dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(v), ctypes.sizeof(v)) == 0 and v.value != 0


def windows_above(hwnd, limit: int = 500) -> list:
    """Screen rects (x, y, w, h) of the windows above ``hwnd`` in the Z order that can hide part of it:
    visible, not minimised, not cloaked, not click-through, not the taskbar. Window-manager information only
    (Z order, style, position – like EnumWindows); no process of any window is touched."""
    if not IS_WIN or not hwnd:
        return []
    out = []
    click_through = WS_EX_LAYERED | WS_EX_TRANSPARENT
    h = user32.GetWindow(hwnd, GW_HWNDPREV)
    steps = 0
    while h and steps < limit:
        steps += 1
        try:
            if (user32.IsWindowVisible(h) and not user32.IsIconic(h) and not _cloaked(h)
                    and (user32.GetWindowLongW(h, GWL_EXSTYLE) & click_through) != click_through
                    and _class_name(h) not in NOT_COVERING):
                r = _outer_rect(h) or _window_rect(h)
                if r and r[2] > 0 and r[3] > 0:
                    out.append(r)
        except Exception:
            pass
        h = user32.GetWindow(h, GW_HWNDPREV)
    return out


def overlaps(box, rects) -> bool:
    """True if the rectangle ``box`` (x, y, w, h) shares pixels with one of ``rects``."""
    x, y, w, h = box
    return any(rx < x + w and x < rx + rw and ry < y + h and y < ry + rh for rx, ry, rw, rh in rects)


# ------------------------------------------------------------------ grabbing
class ScreenGrabber:
    """mss based; create and use it in one thread (GDI handles are per thread)."""

    def __init__(self):
        import mss
        factory = getattr(mss, "MSS", None) or mss.mss      # mss >= 10: MSS, older: mss()
        self._sct = factory()

    def primary_monitor(self):
        m = self._sct.monitors[1] if len(self._sct.monitors) > 1 else self._sct.monitors[0]
        return m["left"], m["top"], m["width"], m["height"]

    def grab(self, left: int, top: int, width: int, height: int) -> np.ndarray:
        shot = self._sct.grab({"left": int(left), "top": int(top), "width": int(width), "height": int(height)})
        arr = np.frombuffer(shot.bgra, dtype=np.uint8).reshape(shot.height, shot.width, 4)
        return arr[:, :, :3].copy()

    def close(self):
        try:
            self._sct.close()
        except Exception:
            pass


class ImageSource:
    """Replays screenshots from a file or folder instead of the screen (testing)."""

    def __init__(self, path: str, interval: float = 0.8):
        if os.path.isdir(path):
            files = sorted(p for p in glob.glob(os.path.join(path, "*"))
                           if p.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")))
        else:
            files = [path]
        self.frames = [f for f in files]
        self.interval = interval
        self._t0 = time.time()
        self._cache = {}
        self._lock = threading.Lock()

    def current(self) -> np.ndarray | None:
        if not self.frames:
            return None
        i = int((time.time() - self._t0) / self.interval) % len(self.frames)
        with self._lock:
            if i not in self._cache:
                img = cv2.imdecode(np.fromfile(self.frames[i], dtype=np.uint8), cv2.IMREAD_COLOR)
                self._cache = {i: img}
            return self._cache[i]
