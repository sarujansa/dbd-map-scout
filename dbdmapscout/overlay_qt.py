"""The overlay as a Qt window: fallback when the native Win32 overlay cannot be made, and the overlay outside
Windows (development, ``--simulate``). Same content as the native one (overlay_win32.PictureOverlay); a frameless,
translucent, always-on-top window that lets clicks through – except in edit mode, where it can be dragged and
the mouse wheel changes the size. Positions are physical pixels like the window rectangles from capture.py."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget

from .overlay_win32 import PictureOverlay

FLAGS = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus


class _Window(QWidget):
    def __init__(self, owner):
        super().__init__(None, FLAGS | Qt.WindowTransparentForInput)
        self.owner = owner
        self.image = None
        self._drag = None
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

    def paintEvent(self, _e):
        if self.image is not None:
            p = QPainter(self)
            p.drawImage(0, 0, self.image)
            p.end()

    def mousePressEvent(self, e):
        if self.owner.editing and e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _e):
        if self._drag is not None:
            self._drag = None
            self.owner._dropped()

    def wheelEvent(self, e):
        if self.owner.editing and self.owner.on_wheel:
            self.owner.on_wheel(1 if e.angleDelta().y() > 0 else -1)


class QtOverlay(PictureOverlay):
    def __init__(self, root):
        super().__init__(root)
        self.win = _Window(self)
        self._start()

    def _ratio(self) -> float:
        return self.win.devicePixelRatioF() or 1.0

    def _push(self, pos=None):
        if not self._prepared:
            return
        data, w, h, _ = self._prepared[self._frame_i]
        img = QImage(data, w, h, w * 4, QImage.Format_ARGB32_Premultiplied).copy()   # BGRA = ARGB32 in memory
        ratio = self._ratio()
        img.setDevicePixelRatio(ratio)
        self.win.image = img
        self.win.setWindowOpacity(self.opacity)
        x, y = pos or self._pos or (0, 0)
        self.win.setGeometry(round(x / ratio), round(y / ratio), max(1, round(w / ratio)), max(1, round(h / ratio)))
        self.win.update()

    def _show_window(self):
        self.win.show()

    def _hide_window(self):
        self.win.hide()

    def _raise(self):
        self.win.raise_()

    def _apply_editing(self):
        shown = self.win.isVisible()
        self.win.setWindowFlags(FLAGS if self._editing else FLAGS | Qt.WindowTransparentForInput)
        if shown:
            self.win.show()                   # changing the flags hides the window

    @property
    def dragging(self) -> bool:
        return self.win._drag is not None

    def _dropped(self):
        ratio = self._ratio()
        p = self.win.pos()
        self._pos = (round(p.x() * ratio), round(p.y() * ratio))
        if self.on_moved:
            self.on_moved(*self._pos)

    def _destroy_window(self):
        self.win.close()
        self.win.deleteLater()

    def hwnd(self) -> int:
        try:
            return int(self.win.winId()) if self.win.isVisible() else 0
        except (RuntimeError, TypeError):
            return 0

    def is_visible(self) -> bool:
        return self.win.isVisible()

