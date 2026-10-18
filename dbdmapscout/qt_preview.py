"""The overlay preview (1.61): the screen with the game picture and bars, every element as a picture; clicks and drags
in edit mode place, pick and size them.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import qt_theme
from .i18n import N_, _
from .qt_common import pixmap_from_pil


PREVIEW_NAMES = {"map": N_("Karte"), "hud": N_("Systemwerte"), "today": N_("Heute"), "music": N_("Musik")}
NOTE_H = 40                      # 1.8.8: the strip below the screen for the note while moving


class PreviewView(QWidget):
    """The overlay tab's screen (since 1.61): the monitor in its shape, the 16:9 game picture with its black bars
    and the map on it where and as big as it will be, with its opacity and the lines below it. A click or a drag
    puts the map there: post("act", (key, ("move", x, y))) in screen pixels – the App makes it the own position."""

    MAX_H = 380

    def __init__(self, key, post):
        super().__init__()
        self._key, self._post = key, post
        self._data = {}
        self._pix = None                       # (picture object, size) -> QPixmap
        self._dragging = False
        self._grab = None                      # (layer name, dx, dy) while an element is dragged
        self._hover = None                     # layer under the mouse while moving (1.64.7)
        self._sizing = None                    # (layer name, x, y, w, h) while its corner is dragged (1.64.9)
        self._snapped = (None, None)           # lines the dragged element snapped to (1.65), drawn as guides
        self._held = None                      # (name, x, y, since) drawn at once (1.65.2, user: it jumped)
        self.setFocusPolicy(Qt.ClickFocus)     # arrow keys after a click (1.65)
        self.setMouseTracking(True)            # open hand over an element
        sp = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)
        self.setMinimumHeight(120)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(_("Klick auf Karte, Systemwerte oder Musik wählt das Element für den Regler „Grösse“. "
                          "Mit „Mit der Maus verschieben“: Element ziehen = verschieben, an der Ecke ziehen oder "
                          "Strg+Mausrad = Grösse, Klick auf eine freie Stelle setzt die Karte dorthin. Ende mit „Fertig“."))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        sw, sh = self._data.get("screen") or (16, 9)
        return min(self.MAX_H, max(120, round(w * sh / max(1, sw)))) + self._note_h()

    def _note_h(self) -> int:
        """1.8.8: in moving mode a strip below the screen holds the note (over the picture it hid the music card)."""
        return NOTE_H if self._data.get("editing") else 0

    def sizeHint(self):
        return QSize(560, self.heightForWidth(560))

    def show_state(self, st):
        data = st.get("data") or {}
        key = {k: v for k, v in data.items() if k != "pics"}
        old = {k: v for k, v in self._data.items() if k != "pics"}
        pics, old_pics = data.get("pics") or {}, self._data.get("pics") or {}
        if key == old and pics.keys() == old_pics.keys() and all(pics[k] is old_pics[k] for k in pics):
            return
        shape = data.get("screen") != self._data.get("screen") or \
            bool(data.get("editing")) != bool(self._data.get("editing"))
        self._data = data
        if self._held and not self._grab:      # dropped: the App's own place counts again
            self._held = None
        if shape:
            self.updateGeometry()
        self.update()

    def _frame(self):
        """(left, top, scale): where the screen is drawn in the widget, screen px -> widget px."""
        sw, sh = self._data.get("screen") or (16, 9)
        height = self.height() - self._note_h()
        s = min(self.width() / max(1, sw), height / max(1, sh))
        return (self.width() - sw * s) / 2, (height - sh * s) / 2, s

    def paintEvent(self, _e):
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QFont, QPainter, QPen
        d = self._data
        if not d.get("screen"):
            return
        sw, sh = d["screen"]
        ox, oy, s = self._frame()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        screen = QRectF(ox, oy, sw * s, sh * s)
        p.setPen(QPen(QColor("#4a4d55"), 1))
        p.setBrush(QColor("#050506"))
        p.drawRoundedRect(screen.adjusted(-1, -1, 1, 1), 4, 4)
        bar = d.get("bar", 0) * s
        game = QRectF(ox + bar, oy, sw * s - 2 * bar, sh * s)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#2b3036"))
        p.drawRect(game)
        p.setPen(QColor("#5c636d"))
        f = QFont(self.font())
        f.setPointSizeF(max(7.0, f.pointSizeF() * 0.9))
        p.setFont(f)
        if not d.get("editing"):                   # moving: the centre cross is there
            p.drawText(game, Qt.AlignCenter, _("Spielbild"))
        # every element as the game shows it (1.64): map + lines, system values, music card – real pictures
        pics = d.get("pics") or {}
        ratio = self.devicePixelRatioF()
        cache = self._pix if isinstance(self._pix, dict) else {}
        fresh = {}
        ops = d.get("opacities") or {}
        for name, lx, ly, lw, lh in self._layers():
            img = pics.get(name)
            if img is None:
                continue
            p.setOpacity(float(ops.get(name, d.get("opacity", 1.0))))     # per element (1.2.7)
            th = max(1, round(lh * s))
            hit = cache.get(name)
            pix = hit[2] if hit and hit[0] is img and hit[1] == th else pixmap_from_pil(img, th, ratio)
            fresh[name] = (img, th, pix)
            p.drawPixmap(round(ox + lx * s), round(oy + ly * s), pix)
        self._pix = fresh
        p.setOpacity(1.0)
        if d.get("editing"):                       # moving is on: a frame round the screen and a note
            accent = QColor(qt_theme.colours(True)["accent"])
            cx, cy = screen.center().x(), screen.center().y()         # centre cross (1.64.5)
            for pen in (QPen(QColor(0, 0, 0, 150), 3), QPen(QColor(255, 255, 255, 220), 1, Qt.DashLine)):
                p.setPen(pen)
                p.drawLine(QPointF(cx, screen.top()), QPointF(cx, screen.bottom()))
                p.drawLine(QPointF(screen.left(), cy), QPointF(screen.right(), cy))
            p.setPen(QPen(accent, 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(screen.adjusted(-1, -1, 1, 1), 4, 4)
            nf = QFont(self.font())
            nf.setBold(True)
            p.setFont(nf)
            p.setPen(accent)
            # 1.8.8: in its own strip below the screen (1.8.2 put it on the picture, where it hid the music card)
            note = _("Verschieben aktiv – ziehen (rastet ein, Alt = frei), Pfeiltasten = fein, Ecke/Strg+Mausrad = Grösse")
            strip = QRectF(screen.left(), screen.bottom() + 4, screen.width(), self.height() - screen.bottom() - 4)
            p.drawText(strip, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, note)
        if d.get("editing"):                       # every element named; the one under the mouse in accent colour
            accent = QColor(qt_theme.colours(True)["accent"])
            held = self._grab[0] if self._grab else self._hover
            tf = QFont(self.font())
            tf.setBold(True)
            tf.setPixelSize(11)
            p.setFont(tf)
            rects = {name: QRectF(ox + lx * s, oy + ly * s, lw * s, lh * s).adjusted(-2, -2, 2, 2)   # 1.8.8: off the text
                     for name, lx, ly, lw, lh in self._layers()}
            for name, r in rects.items():
                on = name == held or name == d.get("selected")
                p.setPen(QPen(accent if on else QColor(255, 255, 255, 140), 2 if on else 1,
                              Qt.SolidLine if on else Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawRect(r)
                tag = _(PREVIEW_NAMES.get(name, name))
                tw = p.fontMetrics().horizontalAdvance(tag) + 8
                tr = QRectF(max(screen.left(), min(r.left(), screen.right() - tw)), max(oy, r.top() - 15), tw, 15)
                if any(tr.intersects(o) for n2, o in rects.items() if n2 != name):
                    tr.moveTop(r.top())               # 1.8.8: no room above (stacked cards): inside its own frame
                p.fillRect(tr, accent if on else QColor(30, 30, 34, 220))
                p.setPen(QColor(20, 16, 4) if on else QColor(235, 235, 235))
                p.drawText(tr, Qt.AlignCenter, tag)
            lx, ly = self._snapped if self._grab else (None, None)
            p.setPen(QPen(accent, 1.5))
            if lx is not None:                     # the line the dragged element snapped to (1.65)
                p.drawLine(QPointF(ox + lx * s, screen.top()), QPointF(ox + lx * s, screen.bottom()))
            if ly is not None:
                p.drawLine(QPointF(screen.left(), oy + ly * s), QPointF(screen.right(), oy + ly * s))
            sel = self._layer(d.get("selected"))
            if sel:                                # the picked element: its corner sizes it (1.64.9)
                hr = self._handle_rect(sel, ox, oy, s)
                p.setPen(QPen(QColor(20, 16, 4), 1))
                p.setBrush(accent)
                p.drawRect(hr)
            if held:
                p.setPen(accent)
                p.setFont(tf)
                what = _("Ziehst: {name}", name=_(PREVIEW_NAMES.get(held, held))) if self._grab else \
                    _("Unter der Maus: {name}", name=_(PREVIEW_NAMES.get(held, held)))
                p.drawText(QRectF(screen.left(), screen.bottom() + 4, screen.width(), self.height() - screen.bottom() - 4),
                           Qt.AlignHCenter | Qt.AlignBottom, what)
        x, y, w, h, _mh = d.get("rect") or (0, 0, 0, 0, 0)
        sel = self._layer(d.get("selected"))
        if sel:                                    # the element the size slider works on (1.64.9)
            _n, x, y, w, h = sel
        if w and h and not d.get("editing"):
            rx, ry = ox + x * s, oy + y * s
            pen = QPen(QColor(qt_theme.colours(True)["accent"]), 1.5, Qt.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(rx, ry, w * s, h * s))
        p.end()

    def contextMenuEvent(self, e):
        """1.8.10: right click on an element: the App shows its quick actions (size, dark area, hide …)."""
        ox, oy, s = self._frame()
        if s <= 0:
            return
        hit = self.layer_at((e.pos().x() - ox) / s, (e.pos().y() - oy) / s)
        if hit is None:
            return
        gp = e.globalPos()
        self._post("act", (self._key, ("menu", hit[0], gp.x(), gp.y())))

    def _screen_pos(self, e):
        ox, oy, s = self._frame()
        pos = e.position()
        return ((pos.x() - ox) / s, (pos.y() - oy) / s) if s > 0 else None

    def _layers(self):
        """The layers as drawn: the one held by the mouse where the mouse has it, not where the App last put it
        (that comes only 4×/s – the element jumped behind the mouse)."""
        held = self._held
        if held and time.monotonic() - held[3] > 1.5 and not self._grab:
            held = self._held = None
        return [(n, held[1], held[2], w, h) if held and n == held[0] else (n, x, y, w, h)
                for n, x, y, w, h in self._data.get("layers") or ()]

    def _layer(self, name):
        return next((lay for lay in self._layers() if lay[0] == name), None)

    HANDLE = 12                                # px (widget): the corner that sizes the picked element

    def _handle_rect(self, layer, ox, oy, s):
        from PySide6.QtCore import QRectF
        _n, lx, ly, lw, lh = layer
        k = self.HANDLE
        return QRectF(ox + (lx + lw) * s - k / 2, oy + (ly + lh) * s - k / 2, k, k)

    def _on_handle(self, e):
        """The picked element when the mouse is on its corner (moving mode only)."""
        sel = self._layer(self._data.get("selected")) if self._data.get("editing") else None
        if sel is None:
            return None
        ox, oy, s = self._frame()
        return sel if self._handle_rect(sel, ox, oy, s).adjusted(-3, -3, 3, 3).contains(e.position()) else None

    def wheelEvent(self, e):
        """Moving mode: Ctrl + wheel over an element sizes it (like over the map in the game); else the page
        scrolls. 1.3.2 (user: "nervt, dass sich die Fenster verstellen, wenn ich mit dem Mausrad drin drehe"):
        the plain wheel never changes a size."""
        ctrl = bool(e.modifiers() & Qt.ControlModifier)
        pt = self._screen_pos(e) if self._data.get("editing") and ctrl else None
        hit = self.layer_at(*pt) if pt else None
        steps = e.angleDelta().y() / 120
        if not hit or not steps:
            e.ignore()
            return
        lay = self._layer(hit[0])
        self._post("act", (self._key, ("resize", hit[0], lay[4] * 1.06 ** steps)))
        e.accept()

    def layer_at(self, x, y):
        """(name, dx, dy) of the topmost element under screen point (x, y), or None (1.64.1)."""
        for name, lx, ly, lw, lh in reversed(self._layers()):
            if lx <= x <= lx + lw and ly <= y <= ly + lh:
                return name, x - lx, y - ly
        return None

    def _move(self, e):
        pt = self._screen_pos(e)
        if pt is None:
            return
        if self._grab:                     # an element held at the place it was grabbed: its corner follows
            name, dx, dy = self._grab
            x, y = pt[0] - dx, pt[1] - dy
            lay = self._layer(name)
            self._snapped = (None, None)
            if lay and not e.modifiers() & Qt.AltModifier:        # 1.65: snaps to centre, bars, other elements
                from .layoutmem import SNAP_PX, snap_lines, snap_rect
                xs, ys = snap_lines(self._data["screen"], self._data.get("bar", 0), self._data.get("layers") or (),
                                    name)
                x, y, lx, ly = snap_rect(x, y, lay[3], lay[4], xs, ys, SNAP_PX / max(1e-6, self._frame()[2]))
                self._snapped = (lx, ly)
            self._held = (name, x, y, time.monotonic())
            self.update()
            self._post("act", (self._key, ("place", name, x, y)))
        else:                              # empty place: the map's centre goes there
            self._post("act", (self._key, ("move", pt[0], pt[1])))

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        corner = self._on_handle(e)
        if corner:
            self._sizing = corner
            return
        pt = self._screen_pos(e)
        hit = self.layer_at(*pt) if pt else None
        if hit:                                # 1.64.9: a click picks the element for the size slider
            self._post("act", (self._key, ("select", hit[0])))
        if self._data.get("editing"):
            self._grab = hit
            self._dragging = True
            self.setCursor(Qt.ClosedHandCursor)
            if not self._grab:
                self._move(e)

    def mouseMoveEvent(self, e):
        if self._sizing:                       # the corner: as big as the mouse is from the top left corner
            pt = self._screen_pos(e)
            if pt:
                name, lx, ly, lw, lh = self._sizing
                f = max((pt[0] - lx) / max(1, lw), (pt[1] - ly) / max(1, lh), 0.05)
                self._post("act", (self._key, ("resize", name, lh * f)))
            return
        if self._dragging:
            self._move(e)
        elif not self._data.get("editing"):
            self.setCursor(Qt.ArrowCursor)
        else:
            pt = self._screen_pos(e)
            hit = self.layer_at(*pt) if pt else None
            self.setCursor(Qt.SizeFDiagCursor if self._on_handle(e) else
                           Qt.OpenHandCursor if hit else Qt.PointingHandCursor)
            if (hit[0] if hit else None) != self._hover:
                self._hover = hit[0] if hit else None
                self.update()

    def leaveEvent(self, _e):
        if self._hover:
            self._hover = None
            self.update()

    def mouseReleaseEvent(self, _e):
        self._dragging = False
        self._grab = self._sizing = None
        if self._held:
            self._held = self._held[:3] + (time.monotonic(),)
        if self._snapped != (None, None):
            self._snapped = (None, None)
            self.update()

    def keyPressEvent(self, e):
        """Arrow keys (moving mode): the picked element by 1 px, with Shift by 10 px (1.65)."""
        step = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}.get(e.key())
        if step is None or not self._data.get("editing") or not self._data.get("selected"):
            super().keyPressEvent(e)
            return
        n = 10 if e.modifiers() & Qt.ShiftModifier else 1
        self._post("act", (self._key, ("nudge", step[0] * n, step[1] * n)))
        e.accept()
        self.setCursor(Qt.PointingHandCursor)
