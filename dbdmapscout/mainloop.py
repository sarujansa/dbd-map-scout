"""The program's main loop (since 1.57: Qt's event loop – Tk is gone).

``MainLoop`` offers what the App and the overlays used from Tk's root: ``after(ms, fn)`` / ``after_cancel(job)``
timers, the clipboard, the system beep and the screen size. Timers run on the main thread; an exception in one
goes to ``on_error`` instead of ending the program. On Windows Qt's loop also dispatches the messages of the
program's own Win32 windows (overlay, system values), as Tcl's did before.
"""
from __future__ import annotations

import collections
import sys
import time
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication

IS_WIN = sys.platform == "win32"
SLOW_MS = 30                # a timer callback this long, or this late, is noted for the diagnosis (window lag)
SLOW_KEPT = 40


def _name(fn) -> str:
    """Readable name of a callback: "App._tick_overlay", lambdas by where they were written."""
    name = getattr(fn, "__qualname__", None) or type(fn).__name__
    if name.endswith("<lambda>"):
        code = getattr(fn, "__code__", None)
        if code is not None:
            name += f" ({code.co_filename.rsplit('/', 1)[-1].rsplit(chr(92), 1)[-1]}:{code.co_firstlineno})"
    return name


class MainLoop:
    def __init__(self, qapp, on_error=None):
        self.qapp = qapp
        self.on_error = on_error
        self._jobs = set()                  # running single-shot timers (a QTimer without a reference is lost)
        # (time, what, took ms, late ms) of slow or late callbacks – "Diagnose kopieren" shows them
        self.slow = collections.deque(maxlen=SLOW_KEPT)

    def after(self, ms, fn):
        t = QTimer()
        t.setSingleShot(True)
        due = time.perf_counter() + max(0, int(ms)) / 1000
        t.timeout.connect(lambda: self._fire(t, fn, due))
        self._jobs.add(t)
        t.start(max(0, int(ms)))
        return t

    def note(self, what: str, took_ms: float, late_ms: float = 0.0):
        """Remember something that held up the window (also used for the App's events)."""
        if took_ms >= SLOW_MS or late_ms >= 2 * SLOW_MS:
            self.slow.append((time.time(), what, took_ms, late_ms))

    def after_cancel(self, job):
        if job is not None:
            job.stop()
            self._jobs.discard(job)

    def _fire(self, t, fn, due=None):
        self._jobs.discard(t)
        start = time.perf_counter()
        try:
            fn()
        except Exception:
            if self.on_error is not None:
                self.on_error(traceback.format_exc())
            else:
                traceback.print_exc()
        late = (start - due) * 1000 if due is not None else 0.0      # the loop was busy elsewhere (paint, Qt …)
        self.note(_name(fn), (time.perf_counter() - start) * 1000, late)

    def clipboard_set(self, text: str):
        QGuiApplication.clipboard().setText(text)

    def clipboard_files(self, paths):
        """1.8.60: files onto the clipboard, as Explorer's "Copy" does – Ctrl+V in Discord or Explorer pastes them."""
        from PySide6.QtCore import QMimeData, QUrl
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(p) for p in paths])
        QGuiApplication.clipboard().setMimeData(data)

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
        """End the loop now. Not QApplication.quit(): in Qt 6 that first asks every window to close, and the control
        window refuses (its X means "quit through the App") – the loop would never end."""
        for t in list(self._jobs):
            t.stop()
        self._jobs.clear()
        self.qapp.exit(0)
