"""Own small notification window bottom right ("Lobby gefunden").

Windows notifications from the tray icon are swallowed by "Do not disturb", which Windows 11 switches
on by itself while a game or a full-screen app runs. This window does not depend on that: always on
top, never takes the focus (WS_EX_NOACTIVATE), gone after a few seconds or on a click. Qt since 1.57.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

IS_WIN = sys.platform == "win32"
BG, FG, DIM, ACCENT = "#1e1f22", "#f2f2f2", "#b5bac1", "#c8102e"
WIDTH = 340                       # px (logical)


class _Window(QWidget):
    def __init__(self, title: str, text: str, on_click):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._on_click = on_click
        self.setStyleSheet(f"QWidget#toast {{ background: {ACCENT}; }} QFrame#body {{ background: {BG}; }}"
                           f"QLabel {{ background: transparent; font-family: 'Segoe UI'; }}")
        self.setObjectName("toast")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 1, 1, 1)               # red frame: 4 px on the left, 1 px around
        body = QFrame()
        body.setObjectName("body")
        outer.addWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)
        head = QLabel(title)
        head.setStyleSheet(f"color: {FG}; font-size: 16px; font-weight: 700;")
        lay.addWidget(head)
        line = QLabel(text)
        line.setWordWrap(True)
        line.setStyleSheet(f"color: {DIM}; font-size: 13px;")
        lay.addWidget(line)
        self.setFixedWidth(WIDTH)

    def mousePressEvent(self, _e):
        self._on_click()


def _no_activate(win):
    """Windows: never the active window, always on top (Qt's flags alone still let a click activate it)."""
    if not IS_WIN:
        return
    try:
        from .overlay import (GWL_EXSTYLE, HWND_TOPMOST, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE, WS_EX_NOACTIVATE,
                              WS_EX_TOOLWINDOW, WS_EX_TOPMOST, _GetLong, _SetLong, _user32)
        h = int(win.winId())
        _SetLong(h, GWL_EXSTYLE, _GetLong(h, GWL_EXSTYLE) | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST)
        _user32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    except Exception:
        pass


class Toast:
    def __init__(self, loop):
        self.loop = loop                  # mainloop.MainLoop (timers)
        self.win = None
        self._job = None
        self.on_rect = None               # 1.8.13: told (x, y, w, h) in screen pixels / None – the worker blacks it out

    @property
    def shown(self) -> bool:
        return self.win is not None

    def show(self, title: str, text: str, seconds: float = 8.0):
        self.close()
        w = self.win = _Window(title, text, self.close)
        w.adjustSize()
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()             # without the taskbar
            w.move(area.right() - w.width() - 16, area.bottom() - w.height() - 16)
        _no_activate(w)
        w.show()
        _no_activate(w)
        if self.on_rect is not None:
            g, dpr = w.frameGeometry(), w.devicePixelRatioF()
            self.on_rect((int(g.x() * dpr) - 4, int(g.y() * dpr) - 4, int(g.width() * dpr) + 8,
                          int(g.height() * dpr) + 8))
        self._job = self.loop.after(int(seconds * 1000), self.close)

    def close(self):
        if self._job is not None:
            self.loop.after_cancel(self._job)
            self._job = None
        if self.win is not None:
            try:
                self.win.close()
            except RuntimeError:              # already deleted by Qt
                pass
            self.win = None
            if self.on_rect is not None:
                self.on_rect(None)
