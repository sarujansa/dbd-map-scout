"""Picture of the DBD window even when other windows lie on top of it.

Windows Graphics Capture (WGC) – the API behind OBS "Window Capture (Windows 10+)":
Windows' compositor (DWM) hands out the picture of one window. Nothing is sent to
the game, its process is never opened, nothing is injected.

Library: windows-capture 2.0.1 (MIT, installed with --no-deps next to
opencv-python-headless). Reviewed: the compiled module imports no OpenProcess,
GetWindowThreadProcessId, hooks, input or memory functions – only window info,
Direct3D and the capture API. Keep that exact version pinned (requirements-extra.txt).

Every picture the library receives is copied from the GPU, so the capture only
runs while it is needed: while DBD is *not* the active window. With DBD active in
front nothing can cover it and the cheap screen capture (mss) is used as before.
"""
from __future__ import annotations

import threading
import time

import cv2

FRAME_INTERVAL_MS = 200      # ask Windows for at most 5 pictures/s (Windows 11 24H2+, else ignored)
WAIT = 0.4                   # longest wait for a fresh picture before falling back to the screen
STALE_PAUSE = 2.0            # after a timeout do not wait again for this long (game draws nothing in background)


class CapturePolicy:
    """When should the window capture run? (pure logic, testable)

    On as soon as DBD is visible but not the active window; off again once DBD has
    been active for STOP_AFTER seconds (quick Alt+Tab back and forth does not
    restart it every time), or when DBD is gone / minimised / the option is off."""
    STOP_AFTER = 5.0

    def __init__(self):
        self.active = False
        self._fg_since = None

    def update(self, t: float, enabled: bool, window_ok: bool, foreground: bool) -> bool:
        if not (enabled and window_ok):
            self.active, self._fg_since = False, None
            return False
        if not foreground:
            self.active, self._fg_since = True, None
        elif self.active:
            self._fg_since = self._fg_since if self._fg_since is not None else t
            if t - self._fg_since >= self.STOP_AFTER:
                self.active, self._fg_since = False, None
        return self.active


class WindowCapture:
    """WGC capture of one window; grab() returns a BGR region in window pixels."""

    def __init__(self, hwnd: int):
        self.hwnd = int(hwnd)
        self.error = ""
        self.closed = False
        self.options = {}
        self.size = None                 # (width, height) of the last picture
        self._ctrl = None
        self._lock = threading.Lock()
        self._want = None                # region asked for by grab(): (x, y, w, h)
        self._out = None
        self._got = threading.Event()
        self._no_wait_until = 0.0

    def start(self) -> bool:
        try:
            from windows_capture import WindowsCapture
        except Exception as e:           # package missing (older installation) or not Windows
            self.error = f"Paket windows-capture nicht verfügbar ({type(e).__name__}: {e})"
            return False

        def on_frame_arrived(frame, capture_control):
            self._on_frame(frame)

        def on_closed():
            self.closed = True
            self._got.set()

        last = None
        # newest options first; each one is refused by older Windows versions -> try without it
        for kw in ({"cursor_capture": False, "draw_border": False, "minimum_update_interval": FRAME_INTERVAL_MS},
                   {"cursor_capture": False, "draw_border": False},
                   {"cursor_capture": False},
                   {"cursor_capture": None}):
            try:
                cap = WindowsCapture(window_hwnd=self.hwnd, **kw)
                cap.event(on_frame_arrived)
                cap.event(on_closed)
                self._ctrl = cap.start_free_threaded()
                self.options = kw
                return True
            except Exception as e:
                last = e
        self.error = f"{type(last).__name__}: {last}"
        return False

    def _on_frame(self, frame) -> None:
        """Runs on the capture thread. The buffer is only valid during this call: copy what grab() wants."""
        with self._lock:
            self.size = (int(frame.width), int(frame.height))
            want, self._want = self._want, None
            if want is None:
                return
            x, y, w, h = want
            self._out = cv2.cvtColor(frame.frame_buffer[y:y + h, x:x + w], cv2.COLOR_BGRA2BGR)   # copy, 1.3.5
        self._got.set()

    def grab(self, x: int, y: int, w: int, h: int, expect_size=None, timeout: float = WAIT):
        """Region of the next picture, or None (no picture in time, closed, or the picture does not have
        the expected window size – e.g. a title bar – so window pixels would not line up)."""
        if self.closed or self._ctrl is None:
            return None
        if expect_size is not None and self.size is not None and self.size != tuple(expect_size):
            return None
        if time.monotonic() < self._no_wait_until:
            return None                  # pictures did not come lately: do not slow the worker down
        self._got.clear()
        with self._lock:
            self._want = (int(x), int(y), int(w), int(h))
        if not self._got.wait(timeout) or self.closed:
            with self._lock:
                self._want = None
            self._no_wait_until = time.monotonic() + STALE_PAUSE
            return None
        if expect_size is not None and self.size != tuple(expect_size):
            return None
        return self._out

    def stop(self) -> None:
        ctrl, self._ctrl = self._ctrl, None
        if ctrl is not None:
            try:
                ctrl.stop()
            except Exception:
                pass
        self.closed = True


def describe(cap: WindowCapture | None, active: bool) -> str:
    """Short text for status/diagnosis."""
    if not active:
        return "Bildschirm"
    if cap is None or cap.closed:
        return "Bildschirm (Fensteraufnahme aus)"
    return f"Fenster (WGC{', 5/s' if 'minimum_update_interval' in cap.options else ''})"
