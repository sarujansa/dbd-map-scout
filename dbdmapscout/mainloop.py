"""The program's main loop (since 1.57: Qt's event loop – Tk is gone).

``MainLoop`` offers what the App and the overlays used from Tk's root: ``after(ms, fn)`` / ``after_cancel(job)``
timers, the clipboard, the system beep and the screen size. Timers run on the main thread; an exception in one
goes to ``on_error`` instead of ending the program. On Windows Qt's loop also dispatches the messages of the
program's own Win32 windows (overlay, system values), as Tcl's did before.
"""
from __future__ import annotations

import sys
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication

IS_WIN = sys.platform == "win32"


class MainLoop:
    def __init__(self, qapp, on_error=None):
        self.qapp = qapp
        self.on_error = on_error
        self._jobs = set()                  # running single-shot timers (a QTimer without a reference is lost)

    def after(self, ms, fn):
        t = QTimer()
        t.setSingleShot(True)
        t.timeout.connect(lambda: self._fire(t, fn))
        self._jobs.add(t)
        t.start(max(0, int(ms)))
        return t

    def after_cancel(self, job):
        if job is not None:
            job.stop()
            self._jobs.discard(job)

    def _fire(self, t, fn):
        self._jobs.discard(t)
        try:
            fn()
        except Exception:
            if self.on_error is not None:
                self.on_error(traceback.format_exc())
            else:
                traceback.print_exc()

    def clipboard_set(self, text: str):
        QGuiApplication.clipboard().setText(text)

    def bell(self):
        if IS_WIN:
            try:
                import winsound
                winsound.MessageBeep()
                return
            except Exception:
                pass
        from PySide6.QtWidgets import QApplication
        QApplication.beep()

    def screen_size(self) -> tuple[int, int]:
        """Primary screen in physical pixels (the program is DPI aware on Windows: window rectangles are too)."""
        if IS_WIN:
            try:
                import ctypes
                u = ctypes.windll.user32
                return int(u.GetSystemMetrics(0)), int(u.GetSystemMetrics(1))
            except Exception:
                pass
        s = QGuiApplication.primaryScreen()
        if s is None:
            return 1920, 1080
        g = s.geometry()
        return round(g.width() * s.devicePixelRatio()), round(g.height() * s.devicePixelRatio())

    def virtual_screen(self) -> tuple[int, int, int, int]:
        """(x, y, w, h) of all screens together."""
        if IS_WIN:
            try:
                import ctypes
                u = ctypes.windll.user32
                return (int(u.GetSystemMetrics(76)), int(u.GetSystemMetrics(77)), int(u.GetSystemMetrics(78)),
                        int(u.GetSystemMetrics(79)))
            except Exception:
                pass
        w, h = self.screen_size()
        return 0, 0, w, h

    def mainloop(self):
        return self.qapp.exec()

    def quit(self):
        for t in list(self._jobs):
            t.stop()
        self._jobs.clear()
        self.qapp.quit()
