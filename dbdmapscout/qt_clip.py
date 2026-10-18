"""The clip editor window (1.5.1, user's wish: cut rounds "wie in Medal"): a preview picture, a timeline with
thumbnails, the F8 marks, a start/end range and a playhead; play/pause (frames streamed by ffmpeg, the sound
by Windows from a WAV of the same stretch), 1-s / 5-s / frame steps, "Clip speichern" (stream copy or frame
exact, see clipedit.cut) into the folder "Clips" next to the recordings.

All ffmpeg work runs in threads (clipedit); results come back over Qt signals. The window is a plain top-level
QWidget the App opens from the tab "Aufnahmen" (app_recordings._rec_clip)."""
from __future__ import annotations

import logging
import os
import threading

from PySide6.QtCore import QObject, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
                               QPushButton, QSizePolicy, QSlider, QVBoxLayout, QWidget)

from . import clipedit, obsrec, qt_theme
from .i18n import N_, _

log = logging.getLogger("dbdmapscout")

CENSOR_LABELS = {"pixel": N_("Verpixelt"), "blur": N_("Verwischt"), "black": N_("Schwarz"),
                 "retouch": N_("Retusche (aus der Umgebung übermalt)")}   # 1.7.2, retouch 1.7.3
COMPACT_PREVIEW_H = 280                          # 1.8.8: picture height of the preview beside the recordings
MIX_MAX = 150                                    # 1.8.6: a source may be raised to 150 %
SOURCE_LABELS = {"dbd": N_("Spiel"), "discord": N_("Discord"), "mic": N_("Mikrofon"), "other": N_("Hintergrund")}
SOURCE_TIPS = {"dbd": N_("Nur der Ton von Dead by Daylight – OBS-Spur 2."),
               "discord": N_("Discord-Sprachchat – OBS-Spur 3. Aus = der Clip hat keinen Discord-Ton."),
               "mic": N_("Dein Mikrofon – OBS-Spur 4 (nur, wenn es in OBS aufgenommen wird)."),
               "other": N_("Andere Programme mit eigener Tonquelle in OBS (z. B. Spotify, Browser) – OBS-Spur 5. Der "
                           "Desktop-Ton von Windows enthält auch DBD und Discord und liegt nur auf Spur 1.")}
ABSENT_TIPS = {"other": N_("In OBS gab es bei dieser Aufnahme keine Hintergrund-Quelle. Für Spotify, Browser & Co. "
                           "in OBS je Programm eine Anwendungs-Audioaufnahme anlegen – das Programm legt sie auf "
                           "Spur 5."),
               "dbd": N_("Diese Tonquelle war bei der Aufnahme unter Einstellungen → Mehr → Aufnahmen mit OBS "
                         "ausgeschaltet.")}
MODE_LABELS = {"copy": N_("Schnell (an Schlüsselbildern, Anfang bis zu ein paar Sekunden früher)"),
               "exact": N_("Genau (Bild neu kodiert, dauert etwas)"),
               "discord": N_("Für Discord (passt unter die Zielgrösse)")}
KEY_HINT = N_("Leertaste Abspielen · ←/→ 1 s · Shift 5 s · Strg 1 Bild · I/O Start/Ende · M Marke · "
              "Pos1/Ende Anfang/Schluss · Entf Kasten weg · Esc schliessen")
STEP_SMALL, STEP_BIG = 1.0, 5.0
LOAD_TIMEOUT_MS = 30000           # 1.8.3: the loading screen gives up after this and frees the window
PREVIEW_MIN = (640, 360)


def _qimage(img) -> QImage:
    """PIL RGB -> QImage (copied: the PIL buffer may go)."""
    img = img.convert("RGB")
    w, h = img.size
    return QImage(img.tobytes(), w, h, w * 3, QImage.Format_RGB888).copy()


class _Bridge(QObject):
    """Signals the worker threads use to reach the window (queued to the GUI thread)."""
    frame = Signal(float, object)         # scrub picture (t, PIL)
    played = Signal(float, object)        # playback picture
    thumb = Signal(int, object)           # strip picture (index, PIL)
    ended = Signal(object)                # the player that ended
    saved = Signal(bool, str, str)        # ok, path, why
    sound = Signal(object, float)         # wav path (or None) ready for a playback from t
    strip_done = Signal()                 # 1.8.3: the thumbnail thread is through (all it could get)
    still = Signal(bool, str)             # 1.8.10: a still picture saved (ok, path)
    levels = Signal(object)               # 1.8.18: {track index: loudest moment in dB}


class Timeline(QWidget):
    """Thumbnail strip with the start/end range, the playhead and the marks. Drag the handles or the playhead,
    click to seek, wheel = ±1 s (Ctrl: ±0.1 s)."""
    HANDLE = 7
    TOP = 12
    changed = Signal()                    # start/end moved
    seek = Signal(float)                  # the user wants this moment
    picked = Signal(str, float)           # 1.8.10: a line of the right-click menu, at that moment

    def __init__(self, dark=True):
        super().__init__()
        self.duration = 1.0
        self.pos = 0.0
        self.start, self.end = 0.0, 1.0
        self.marks = []
        self.thumbs = {}
        self.n_thumbs = clipedit.THUMBS
        self.dark = dark
        self._drag = None                 # "start" / "end" / "pos"
        self.setMinimumHeight(clipedit.THUMB_H + self.TOP + 4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

    # ---- data
    def set_duration(self, d: float):
        self.duration = max(0.1, float(d))
        self.end = min(self.end, self.duration) if self.end > 0 else self.duration
        self.update()

    def set_range(self, start: float, end: float):
        start = min(max(0.0, start), self.duration)
        end = min(max(start + 0.1, end), self.duration)
        if (start, end) != (self.start, self.end):
            self.start, self.end = start, end
            self.update()
            self.changed.emit()

    def set_position(self, t: float):
        self.pos = min(max(0.0, t), self.duration)
        self.update()

    def set_thumb(self, i: int, img):
        self.thumbs[i] = _qimage(img)
        self.update()

    # ---- geometry
    def _strip(self) -> QRectF:
        return QRectF(self.HANDLE, self.TOP, self.width() - 2 * self.HANDLE, self.height() - self.TOP - 2)

    def _x(self, t: float) -> float:
        r = self._strip()
        return r.left() + r.width() * (t / self.duration)

    def _t(self, x: float) -> float:
        r = self._strip()
        return min(max(0.0, (x - r.left()) / max(1.0, r.width()) * self.duration), self.duration)

    # ---- drawing
    def paintEvent(self, e):
        c = qt_theme.colours(self.dark)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self._strip()
        p.fillRect(r, QColor(c["field"]))
        n = max(1, self.n_thumbs)
        for i in range(n):
            img = self.thumbs.get(i)
            x0, x1 = r.left() + r.width() * i / n, r.left() + r.width() * (i + 1) / n
            if img is not None:
                target = QRectF(x0, r.top(), x1 - x0, r.height())
                p.drawImage(target, img, QRectF(0, 0, img.width(), img.height()))
        shade = QColor(0, 0, 0, 150)
        p.fillRect(QRectF(r.left(), r.top(), self._x(self.start) - r.left(), r.height()), shade)
        p.fillRect(QRectF(self._x(self.end), r.top(), r.right() - self._x(self.end), r.height()), shade)
        accent = QColor(c["accent"])
        p.setPen(QPen(accent, 2))
        p.setBrush(accent)
        for m in self.marks:                                  # marks: small triangles above the strip
            x = self._x(m)
            p.drawPolygon([QRectF(x - 4, 0, 8, self.TOP - 2).topLeft(), QRectF(x - 4, 0, 8, self.TOP - 2).topRight(),
                           QRectF(x - 4, 0, 8, self.TOP - 2).center() + (QRectF(0, 0, 0, self.TOP - 2).bottomLeft())])
        for t in (self.start, self.end):                      # handles
            x = self._x(t)
            p.drawRoundedRect(QRectF(x - self.HANDLE / 2, r.top() - 2, self.HANDLE, r.height() + 4), 2, 2)
        p.setPen(QPen(accent, 2))
        p.drawLine(self._x(self.start), r.top(), self._x(self.end), r.top())
        p.drawLine(self._x(self.start), r.bottom(), self._x(self.end), r.bottom())
        p.setPen(QPen(QColor("#ffffff"), 2))                  # playhead
        x = self._x(self.pos)
        p.drawLine(x, r.top() - 4, x, r.bottom() + 2)
        p.end()

    # ---- mouse
    def _hit(self, x: float):
        for name, t in (("start", self.start), ("end", self.end)):
            if abs(self._x(t) - x) <= self.HANDLE:
                return name
        return "pos"

    def contextMenuEvent(self, e):
        """1.8.10: right click on the strip: the clip starts/ends here, the playhead here, a still picture."""
        from PySide6.QtWidgets import QMenu
        if self.duration <= 0:
            return
        t = self._t(e.pos().x())
        menu = QMenu(self)
        for ident, label in (("seek", _("Abspielkopf hierher")), ("start", _("Clip beginnt hier")),
                             ("end", _("Clip endet hier")), (None, None), ("still", _("Standbild hier speichern"))):
            if ident is None:
                menu.addSeparator()
                continue
            menu.addAction(f"{label}  ({clipedit.fmt_pos(t)})").triggered.connect(
                lambda _c=False, i=ident: self.picked.emit(i, t))
        self._menu = menu
        menu.popup(e.globalPos())

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        self._drag = self._hit(e.position().x())
        self.mouseMoveEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag is None:
            return
        t = self._t(e.position().x())
        if self._drag == "start":
            self.set_range(min(t, self.end - 0.1), self.end)
            self.seek.emit(self.start)
        elif self._drag == "end":
            self.set_range(self.start, max(t, self.start + 0.1))
            self.seek.emit(self.end)
        else:
            self.set_position(t)
            self.seek.emit(t)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def wheelEvent(self, e):
        step = 0.1 if e.modifiers() & Qt.ControlModifier else STEP_SMALL
        d = e.angleDelta().y()
        if d:
            t = self.pos + (step if d > 0 else -step)
            self.set_position(t)
            self.seek.emit(self.pos)
        e.accept()


class PreviewView(QWidget):
    """1.7.2: the picture, letterboxed on a dark rounded area, with the censor boxes drawn over it the way the
    saved clip will look (pixel blocks / blur / black). With the tool on (``editing``) a drag on free picture
    draws a new box, a drag inside a box moves it, its bottom-right corner resizes it, a click picks it."""
    boxes_changed = Signal()
    HANDLE = 10
    MIN_BOX = 0.01                        # fractions of the picture: smaller drags are dropped

    def __init__(self, dark=True):
        super().__init__()
        self.dark = dark
        self._img = None                  # QImage of the frame
        self._scaled = None               # (size, QImage) cache of the frame at the drawn size
        self.boxes = []                   # [[x, y, w, h] …] fractions of the picture
        self.style = "pixel"
        self.active = False               # boxes are applied when saving (and shown applied here)
        self.editing = False              # the tool is on: boxes can be drawn/moved
        self.selected = None
        self._drag = None                 # (kind, press point, original box)
        self.setMinimumSize(*PREVIEW_MIN)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(True)

    # ---- data
    def pixmap(self) -> QPixmap:
        return QPixmap.fromImage(self._img) if self._img is not None else QPixmap()

    def set_frame(self, img: QImage):
        self._img, self._scaled = img, None
        self.update()

    def set_boxes(self, boxes):
        self.boxes = [list(map(float, b)) for b in boxes if len(b) == 4]
        self.selected = None
        self.update()

    def set_editing(self, on: bool):
        self.editing = bool(on)
        self.setCursor(Qt.CrossCursor if self.editing else Qt.ArrowCursor)
        if not self.editing:
            self.selected = None
        self.update()

    def set_look(self, active: bool, style: str):
        self.active, self.style = bool(active), style
        self.update()

    def add_box(self, box, select=True):
        self.boxes.append(list(map(float, box)))
        if select:
            self.selected = len(self.boxes) - 1
        self.update()
        self.boxes_changed.emit()

    def remove_selected(self) -> bool:
        if self.selected is None or not (0 <= self.selected < len(self.boxes)):
            return False
        del self.boxes[self.selected]
        self.selected = None
        self.update()
        self.boxes_changed.emit()
        return True

    def clear_boxes(self):
        if self.boxes:
            self.boxes, self.selected = [], None
            self.update()
            self.boxes_changed.emit()

    # ---- geometry
    def frame_rect(self) -> QRectF:
        """Where the picture lies (aspect kept, centred); 16:9 while there is no picture yet."""
        area = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        iw, ih = (self._img.width(), self._img.height()) if self._img is not None else (16, 9)
        if iw <= 0 or ih <= 0:
            return area
        s = min(area.width() / iw, area.height() / ih)
        w, h = iw * s, ih * s
        return QRectF(area.center().x() - w / 2, area.center().y() - h / 2, w, h)

    def _box_rect(self, box) -> QRectF:
        f = self.frame_rect()
        x, y, w, h = box
        return QRectF(f.left() + x * f.width(), f.top() + y * f.height(), w * f.width(), h * f.height())

    def _to_frac(self, pt) -> tuple:
        f = self.frame_rect()
        return (min(max(0.0, (pt.x() - f.left()) / max(1.0, f.width())), 1.0),
                min(max(0.0, (pt.y() - f.top()) / max(1.0, f.height())), 1.0))

    # ---- drawing
    def _frame_scaled(self, size):
        if self._scaled is None or self._scaled[0] != size:
            self._scaled = (size, self._img.scaled(size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        return self._scaled[1]

    def paintEvent(self, e):
        c = qt_theme.colours(self.dark)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#000000"))
        p.drawRoundedRect(QRectF(self.rect()), 8, 8)
        f = self.frame_rect()
        if self._img is None:
            p.end()
            return
        size = f.toRect().size()
        if size.width() < 2 or size.height() < 2:
            p.end()
            return
        scaled = self._frame_scaled(size)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(f.topLeft(), scaled)
        accent = QColor(c["accent"])
        for i, box in enumerate(self.boxes):
            r = self._box_rect(box)
            if self.active:
                self._draw_censored(p, scaled, r, f)
            if self.editing or not self.active:
                pen = QPen(accent if i == self.selected else QColor(255, 255, 255, 170), 2 if i == self.selected else 1)
                if not self.active:
                    pen.setStyle(Qt.DashLine)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawRect(r)
                if self.editing:
                    p.setBrush(accent if i == self.selected else QColor(255, 255, 255, 200))
                    p.setPen(Qt.NoPen)
                    p.drawRect(QRectF(r.right() - self.HANDLE / 2, r.bottom() - self.HANDLE / 2, self.HANDLE, self.HANDLE))
        if self.editing and self._drag and self._drag[0] == "new":
            p.setPen(QPen(accent, 1, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(self._box_rect(self._drag[2]))
        p.end()

    def _draw_censored(self, p, scaled, r, f):
        """The box as the clip will show it: coarse blocks, a blur, or black (same rules as clipedit.censor_graph)."""
        if self.style == "black":
            p.fillRect(r, QColor("#000000"))
            return
        src = QRectF(r.left() - f.left(), r.top() - f.top(), r.width(), r.height()).toRect() \
            .intersected(scaled.rect())
        if src.width() < 2 or src.height() < 2:
            return
        if self.style == "retouch":        # delogo-like: a smooth fill from the pixels around the box
            m = max(2, min(src.width(), src.height()) // 6)
            around = scaled.copy(src.adjusted(-m, -m, m, m).intersected(scaled.rect()))
            look = around.scaled(2, 2, Qt.IgnoreAspectRatio, Qt.SmoothTransformation) \
                .scaled(src.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            p.drawImage(QRectF(src).translated(f.left(), f.top()).topLeft(), look)
            return
        part = scaled.copy(src)
        if self.style == "blur":
            small = part.scaled(max(1, src.width() // 6), max(1, src.height() // 6), Qt.IgnoreAspectRatio,
                                Qt.SmoothTransformation)
            look = small.scaled(src.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        else:
            blk = max(2, min(src.width(), src.height()) // 8)
            small = part.scaled(max(1, src.width() // blk), max(1, src.height() // blk), Qt.IgnoreAspectRatio,
                                Qt.SmoothTransformation)
            look = small.scaled(src.size(), Qt.IgnoreAspectRatio, Qt.FastTransformation)
        p.drawImage(QRectF(src).translated(f.left(), f.top()).topLeft(), look)

    # ---- mouse (tool on)
    def _hit(self, pt):
        for i in reversed(range(len(self.boxes))):
            r = self._box_rect(self.boxes[i])
            if QRectF(r.right() - self.HANDLE, r.bottom() - self.HANDLE, 2 * self.HANDLE, 2 * self.HANDLE).contains(pt):
                return "resize", i
            if r.contains(pt):
                return "move", i
        return None, None

    def mousePressEvent(self, e):
        if not self.editing or e.button() != Qt.LeftButton or self._img is None:
            return
        pt = e.position()
        kind, i = self._hit(pt)
        if kind is None:
            if not self.frame_rect().contains(pt):
                return
            fx, fy = self._to_frac(pt)
            self.selected = None
            self._drag = ("new", (fx, fy), [fx, fy, 0.0, 0.0])
        else:
            self.selected = i
            self._drag = (kind, self._to_frac(pt), list(self.boxes[i]))
        self.update()

    def mouseMoveEvent(self, e):
        if not self.editing:
            return
        if self._drag is None:
            kind, _i = self._hit(e.position())
            self.setCursor(Qt.SizeFDiagCursor if kind == "resize" else Qt.SizeAllCursor if kind == "move"
                           else Qt.CrossCursor)
            return
        kind, (px, py), orig = self._drag
        fx, fy = self._to_frac(e.position())
        if kind == "new":
            x0, y0 = min(px, fx), min(py, fy)
            self._drag = (kind, (px, py), [x0, y0, abs(fx - px), abs(fy - py)])
        elif kind == "move":
            w, h = orig[2], orig[3]
            x = min(max(0.0, orig[0] + fx - px), 1.0 - w)
            y = min(max(0.0, orig[1] + fy - py), 1.0 - h)
            self.boxes[self.selected] = [x, y, w, h]
        else:
            w = min(max(self.MIN_BOX, orig[2] + fx - px), 1.0 - orig[0])
            h = min(max(self.MIN_BOX, orig[3] + fy - py), 1.0 - orig[1])
            self.boxes[self.selected] = [orig[0], orig[1], w, h]
        self.update()

    def mouseReleaseEvent(self, e):
        if self._drag is None:
            return
        kind, _p, box = self._drag
        self._drag = None
        if kind == "new":
            if box[2] >= self.MIN_BOX and box[3] >= self.MIN_BOX:
                self.add_box(box)
            else:
                self.update()
            return
        self.update()
        self.boxes_changed.emit()


class LoadingScreen(QWidget):
    """1.8.3 (user's wish): a screen over the editor while the clip loads – the first picture and the strip of
    thumbnails come from ffmpeg threads and took a few seconds on long recordings, during which the window
    looked broken (black picture, empty strip). Shows the file name and a bar; ``finish()`` fades it away."""

    def __init__(self, parent, name: str, total: int):
        super().__init__(parent)
        self.total = max(1, total)
        self.done_n = 0
        self.finished = False
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("LoadingScreen { background: rgba(14, 15, 18, 215); }")
        outer = QVBoxLayout(self)
        outer.addStretch()
        row = QHBoxLayout()
        row.addStretch()
        card = QFrame()
        card.setProperty("class", "card")
        card.setMinimumWidth(380)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(22, 18, 22, 18)
        cl.setSpacing(8)
        self.title = QLabel(_("Clip wird geladen …"))
        self.title.setProperty("class", "kpi")
        cl.addWidget(self.title)
        self.name = QLabel(name)
        self.name.setProperty("class", "dim")
        self.name.setWordWrap(True)
        cl.addWidget(self.name)
        self.bar = QProgressBar()
        self.bar.setRange(0, self.total)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        cl.addWidget(self.bar)
        self.detail = QLabel("")
        self.detail.setProperty("class", "dim")
        self.detail.setWordWrap(True)
        cl.addWidget(self.detail)
        row.addWidget(card)
        row.addStretch()
        outer.addLayout(row)
        outer.addStretch()
        self.progress(0, _("Vorschaubild und Zeitleiste kommen aus der Aufnahme."))

    def progress(self, n: int, text: str):
        self.done_n = min(self.total, n)
        self.bar.setValue(self.done_n)
        self.detail.setText(text)

    def finish(self, late: bool = False):
        """Done (or given up): the screen goes away; ``late`` = the timeout, not completion."""
        if self.finished:
            return
        self.finished = True
        self.hide()
        if late:
            self.detail.setText(_("Lädt länger als erwartet – das Fenster ist trotzdem bedienbar."))


class ClipWindow(QWidget):
    """One editor per recording. ``on_saved(path)`` / ``on_setting(key, value)`` / ``log(text, kind)`` come from
    the App; ``mode``/``sound`` are the remembered settings."""

    def __init__(self, path: str, marks: list, clips_dir: str, mode: str = "copy", sound: bool = True,
                 on_saved=None, on_setting=None, log=None, dark=True, qss: str = "", title: str = "",
                 target_mb: int = clipedit.DEFAULT_TARGET_MB, censor_on: bool = False, censor_style: str = "pixel",
                 censor_boxes=(), mix_on=None, mix_vol=None, compact=False, parent=None, on_expand=None, sources=None):
        # 1.8.8: compact = the preview beside the recordings table (no window of its own, no censor card, sound
        # sources only on/off, start/end in the clip card); "Grosser Editor" (on_expand) opens the full window
        super().__init__(parent, Qt.Widget if compact else Qt.Window)
        self.compact, self.on_expand = bool(compact), on_expand
        self.path, self.marks, self.clips_dir = path, sorted(float(m) for m in marks or ()), clips_dir
        self.on_saved, self.on_setting, self.log = on_saved, on_setting, (log or (lambda text, kind="System": None))
        self.saved_seconds = {}           # 1.8.13: out path -> length of the clip (the clips list shows it)
        self.dark = dark
        self.info = clipedit.probe(path)
        self.ffmpeg = clipedit.ffmpeg_exe()
        self.bridge = _Bridge()
        self.player = None
        self.playing = False
        self._wav = None
        self._want = None                   # latest scrub moment asked for: (t, quick first look?)
        self._first_look = True             # 1.8.3: the first picture comes as a key frame at once, exact after
        self._scrub_lock = threading.Condition()
        self._closed = False
        self._target_mb = int(target_mb) if target_mb in clipedit.TARGETS_MB else clipedit.DEFAULT_TARGET_MB
        self._last_out = None               # 1.6.1: the clip saved last (Explorer button)
        self._play_to = None                # 1.6.1: "Clip ansehen" plays start..end, then back to the start
        self._censor_on, self._censor_style = bool(censor_on), censor_style        # 1.7.2: remembered boxes
        self._censor_boxes = [list(b) for b in (censor_boxes or ()) if len(b) == 4]
        self._mix_on = {k: bool((mix_on or {}).get(k, True)) for k in obsrec.SOURCES}     # 1.8.6: sound mix
        self._mix_vol = {k: int((mix_vol or {}).get(k, 100) or 0) for k in obsrec.SOURCES}
        self._sources = obsrec.track_sources(self.info.audio_tracks)
        self._silent = set()                # 1.8.18: sources whose own track holds nothing in this recording
        # 1.8.23: the sources OBS had on their own track when the round was recorded (None = not known: older
        # recordings) – a silent track of a source that was not there says "keine Quelle", not "still"
        self._recorded = None if sources is None else set(sources)
        self._absent = set()
        self.setObjectName("page")
        self.setWindowTitle(title or _("Clip bearbeiten – {name}", name=os.path.basename(path)))
        if qss:
            self.setStyleSheet(qss)
        self._build(mode, sound)
        if not self.compact:
            self.resize(1100, 780)
            self.setMinimumSize(760, 600)
        self.setFocusPolicy(Qt.StrongFocus)
        self.loading = None                 # 1.8.3: LoadingScreen until picture + strip are there
        self._load_state = {"frame": False, "strip": False, "thumbs": 0}
        if not self.info.ok or not self.ffmpeg:
            self.status.setText(_("Datei nicht lesbar oder ffmpeg fehlt – keine Vorschau."))
            self.save_btn.setEnabled(False)
            return
        self.loading = LoadingScreen(self, os.path.basename(path), self.timeline.n_thumbs + 1)
        self.loading.setGeometry(self.rect())
        self.loading.raise_()
        QTimer.singleShot(LOAD_TIMEOUT_MS, lambda: self.loading is not None and self.loading.finish(late=True))
        self.timeline.set_duration(self.info.duration)
        self.timeline.marks = self.marks
        self.timeline.set_range(0.0, self.info.duration)
        first = self.marks[0] if self.marks else 0.0
        if self.marks:                                        # a mark: the clip starts 20 s before it, ends 10 s after
            self.timeline.set_range(max(0.0, first - 20), min(self.info.duration, first + 10))
        self._show_range()
        self._start_threads()
        self.goto(self.timeline.start)

    # ---- building
    def _build(self, mode, sound):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)
        self.preview = PreviewView(self.dark)
        self.preview.boxes_changed.connect(self._boxes_changed)
        if self.compact:                                  # beside the table: the whole editor fits a screen
            self.preview.setMinimumSize(320, 180)
            self.preview.setMaximumHeight(COMPACT_PREVIEW_H)
        lay.addWidget(self.preview, 1)
        self.timeline = Timeline(self.dark)
        self.timeline.seek.connect(self.goto)
        self.timeline.picked.connect(self._timeline_pick)
        self.timeline.changed.connect(self._show_range)
        lay.addWidget(self.timeline)

        # transport: position left, playback in the middle, start/end/mark right
        row = QHBoxLayout()
        self.pos_label = QLabel("")
        self.pos_label.setProperty("class", "dim")
        self.pos_label.setMinimumWidth(150)
        row.addWidget(self.pos_label)
        row.addStretch()
        self.b_back5 = self._btn(row, "−5 s", lambda: self.step(-STEP_BIG), _("5 Sekunden zurück (Shift+←)"))
        self.b_back1 = self._btn(row, "−1 s", lambda: self.step(-STEP_SMALL), _("1 Sekunde zurück (←)"))
        self.play_btn = self._btn(row, _("▶ Abspielen"), self.toggle_play, _("Abspielen / Pause (Leertaste)"))
        self.play_btn.setObjectName("primary")
        self.play_btn.setMinimumWidth(120)
        self.b_fwd1 = self._btn(row, "+1 s", lambda: self.step(STEP_SMALL), _("1 Sekunde vor (→)"))
        self.b_fwd5 = self._btn(row, "+5 s", lambda: self.step(STEP_BIG), _("5 Sekunden vor (Shift+→)"))
        row.addStretch()
        if self.compact:                                  # narrow: ±1 s by keys only, start/end in the clip card
            self.b_back1.hide()
            self.b_fwd1.hide()
            self.pos_label.setMinimumWidth(0)
        else:
            self._range_buttons(row)
        lay.addLayout(row)

        # two cards: the clip (range, size, "Clip ansehen") and the censor boxes (1.7.2)
        cards = QHBoxLayout()
        cards.setSpacing(10)
        clip_card, cl = self._card(_("Clip"))
        self.range_label = QLabel("")
        self.range_label.setProperty("class", "big")
        cl.addWidget(self.range_label)
        self.size_label = QLabel("")
        self.size_label.setProperty("class", "dim")
        self.size_label.setWordWrap(True)
        cl.addWidget(self.size_label)
        cl.addStretch()
        wr = QHBoxLayout()
        self.watch_btn = self._btn(wr, _("▶ Clip ansehen"), self.watch_clip,
                                   _("Spielt genau den Ausschnitt ab und springt danach an seinen Anfang zurück."))
        if self.compact:
            self._range_buttons(wr)
        wr.addStretch()
        cl.addLayout(wr)
        cards.addWidget(clip_card, 1)

        censor_card, zl = self._card(_("Zensieren"))
        zr = QHBoxLayout()
        self.censor_box = QCheckBox(_("Beim Speichern anwenden"))
        self.censor_box.setChecked(self._censor_on)
        self.censor_box.setToolTip(_("Die Kästen werden im gespeicherten Clip unkenntlich gemacht (dafür wird das "
                                     "Bild neu kodiert, auch im Format „Schnell“)."))
        self.censor_box.toggled.connect(self._censor_toggled)
        zr.addWidget(self.censor_box)
        self.style_box = QComboBox()
        for key in clipedit.CENSOR_STYLES:
            self.style_box.addItem(_(CENSOR_LABELS[key]), key)
        self.style_box.setCurrentIndex(max(0, list(clipedit.CENSOR_STYLES).index(self._censor_style)
                                           if self._censor_style in clipedit.CENSOR_STYLES else 0))
        self.style_box.currentIndexChanged.connect(self._censor_style_changed)
        zr.addWidget(self.style_box)
        zr.addStretch()
        zl.addLayout(zr)
        zb = QHBoxLayout()
        self.tool_btn = self._btn(zb, _("Kasten zeichnen"), self._tool_toggled,
                                  _("Im Bild einen Bereich aufziehen; Kästen lassen sich verschieben und an der "
                                    "Ecke rechts unten vergrössern. Nochmal drücken beendet das Werkzeug."))
        self.tool_btn.setCheckable(True)
        self.tool_btn.setProperty("class", "seg")       # checked = accent, like Original/Dunkel on the Maps page
        self.names_btn = self._btn(zb, _("Namen links unten"), self._add_names_box,
                                   _("Setzt einen Kasten dorthin, wo DBD die Namen der Survivor zeigt (links unten "
                                     "im Spielbild) – bei Bedarf verschieben."))
        self.remove_btn = self._btn(zb, _("Kasten entfernen"), self._remove_box,
                                    _("Entfernt den markierten Kasten (Taste Entf)."))
        self.clear_btn = self._btn(zb, _("Alle entfernen"), self._clear_boxes, "")
        zb.addStretch()
        zl.addLayout(zb)
        self.censor_hint = QLabel("")
        self.censor_hint.setProperty("class", "dim")
        self.censor_hint.setWordWrap(True)
        zl.addWidget(self.censor_hint)
        zl.addStretch()
        cards.addWidget(censor_card, 1)
        censor_card.setVisible(not self.compact)          # censor boxes: in the full editor
        lay.addLayout(cards)

        # export: name, format, target size, sound; save / show / folder
        export_card, el = self._card(_("Speichern"))
        row2 = QHBoxLayout()
        row2.addWidget(QLabel(_("Name")))
        self.name_edit = QLineEdit()
        row2.addWidget(self.name_edit, 1)
        if self.compact:                                  # narrow: the format on a line of its own
            el.addLayout(row2)
            row2 = QHBoxLayout()
        row2.addWidget(QLabel(_("Format")))
        self.mode_box = QComboBox()
        if self.compact:
            self.mode_box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            self.mode_box.setMinimumContentsLength(18)
        for key in clipedit.MODES:
            self.mode_box.addItem(_(MODE_LABELS[key]), key)
        self.mode_box.setCurrentIndex(max(0, list(clipedit.MODES).index(mode) if mode in clipedit.MODES else 0))
        self.mode_box.currentIndexChanged.connect(self._mode_changed)
        row2.addWidget(self.mode_box)
        self.target_box = QComboBox()
        for mb in clipedit.TARGETS_MB:
            self.target_box.addItem(_("≤ {n} MB", n=mb), mb)
        self.target_box.setCurrentIndex(list(clipedit.TARGETS_MB).index(self._target_mb))
        self.target_box.setToolTip(_("Discord: ohne Nitro 10 MB, Nitro Basic 50 MB, Nitro 500 MB."))
        self.target_box.currentIndexChanged.connect(self._target_changed)
        row2.addWidget(self.target_box)
        self.sound_box = QCheckBox(_("Ton"))
        self.sound_box.setChecked(bool(sound))
        self.sound_box.setToolTip(_("Beim Abspielen den Ton der Aufnahme mitlaufen lassen (Windows)."))
        self.sound_box.toggled.connect(lambda v: self._setting("clip_sound", bool(v)))
        row2.addWidget(self.sound_box)
        if self.compact:
            row2.addStretch()
        el.addLayout(row2)
        el.addLayout(self._mix_row())                                               # 1.8.6: the sound mix
        row3 = QHBoxLayout()
        self.save_btn = self._btn(row3, _("Clip speichern"), self.save, _("Schreibt den Ausschnitt als MP4 in den Ordner „Clips“ neben den Aufnahmen."))
        self.save_btn.setObjectName("primary")
        self.show_btn = self._btn(row3, _("Im Explorer zeigen"), self._show_saved, _("Zeigt den zuletzt gespeicherten Clip im Explorer."))
        self.show_btn.setEnabled(False)
        self.open_btn = self._btn(row3, _("Clips-Ordner öffnen"), self._open_clips, _("Öffnet den Ordner „Clips“ im Explorer."))
        self.expand_btn = None
        if self.compact:
            self.open_btn.hide()
            self.expand_btn = self._btn(row3, _("Grosser Editor …"), self._expand,
                                        _("Öffnet den Clip im eigenen Fenster – mit Zensieren, Lautstärke je Tonquelle "
                                          "und allen Tasten."))
        self.status = QLabel("")
        self.status.setProperty("class", "dim")
        self.status.setWordWrap(True)
        row3.addWidget(self.status, 1)
        el.addLayout(row3)
        lay.addWidget(export_card)
        hint = QLabel(_(KEY_HINT))
        hint.setProperty("class", "dim")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        hint.setVisible(not self.compact)
        self.preview.set_boxes(self._censor_boxes)
        self.preview.set_look(self._censor_on, self.style_box.currentData() or "pixel")
        self._censor_hint()
        self._mode_changed(self.mode_box.currentIndex(), save=False)

    def _range_buttons(self, row):
        self._btn(row, _("Start setzen"), self.set_start, _("Der Clip beginnt am Abspielkopf (Taste I)."))
        self._btn(row, _("Ende setzen"), self.set_end, _("Der Clip endet am Abspielkopf (Taste O)."))
        self.mark_btn = self._btn(row, _("Zur Marke ▸"), self.next_mark, _("Springt zur nächsten F8-Marke (Taste M)."))
        self.mark_btn.setEnabled(bool(self.marks))

    def _expand(self):
        """1.8.8: compact preview → the full editor (same range and position); this one stops playing."""
        if self.playing:
            self._play_to = None
            self._stop_player()
        if self.on_expand is not None:
            self.on_expand(self.timeline.start, self.timeline.end, self.timeline.pos)

    def stop(self):
        """1.8.8: stop playback (the recordings tab was left)."""
        if self.playing:
            self._play_to = None
            self._stop_player()

    @staticmethod
    def _card(title):
        """A card like the main window's, with a small heading; returns (frame, its layout)."""
        card = QFrame()
        card.setProperty("class", "card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(6)
        head = QLabel(title.upper())
        head.setProperty("class", "sub")
        lay.addWidget(head)
        return card, lay

    # ---- censor boxes (1.7.2)
    def _censor_toggled(self, on):
        self._censor_on = bool(on)
        self.preview.set_look(self._censor_on, self.style_box.currentData() or "pixel")
        self._setting("clip_censor_on", self._censor_on)
        self._censor_hint()
        self._show_size()

    def _censor_style_changed(self, _i):
        style = self.style_box.currentData() or "pixel"
        self.preview.set_look(self._censor_on, style)
        self._setting("clip_censor_style", style)

    def _tool_toggled(self):
        self.preview.set_editing(self.tool_btn.isChecked())
        self._censor_hint()

    def _add_names_box(self):
        self.preview.add_box(clipedit.names_box(self.info.width, self.info.height))
        if not self.censor_box.isChecked():
            self.censor_box.setChecked(True)

    def _remove_box(self):
        if not self.preview.remove_selected() and self.preview.boxes:
            self.preview.selected = len(self.preview.boxes) - 1
            self.preview.remove_selected()

    def _clear_boxes(self):
        self.preview.clear_boxes()

    def _boxes_changed(self):
        self._setting("clip_censor_boxes", [[round(v, 4) for v in b] for b in self.preview.boxes])
        self._censor_hint()
        self._show_size()

    def _censor_hint(self):
        n = len(self.preview.boxes)
        if not n:
            text = _("Noch kein Kasten. „Namen links unten“ setzt einen auf die Survivor-Namen, „Kasten zeichnen“ "
                     "lässt dich einen aufziehen.")
        elif self.preview.editing:
            text = _("{n} Kasten/Kästen – ziehen = verschieben, Ecke rechts unten = Grösse, Klick = markieren.", n=n)
        else:
            text = _("{n} Kasten/Kästen gemerkt – sie gelten auch für den nächsten Clip.", n=n)
        self.censor_hint.setText(text)
        self.remove_btn.setEnabled(n > 0)
        self.clear_btn.setEnabled(n > 0)

    def _censor_args(self) -> dict:
        if self._censor_on and self.preview.boxes:
            return {"censor": [tuple(b) for b in self.preview.boxes],
                    "censor_style": self.style_box.currentData() or "pixel"}
        return {}

    def _btn(self, row, text, slot, tip=""):
        b = QPushButton(text)
        b.setFocusPolicy(Qt.NoFocus)                      # the keys stay with the window
        b.clicked.connect(slot)
        if tip:
            b.setToolTip(tip)
        row.addWidget(b)
        return b

    # ---- 1.8.6: the sound mix (like Medal – each source on its own OBS track, on/off and a level each)
    def _mix_row(self):
        row = QHBoxLayout()
        self.mix_label = QLabel(_("Ton im Clip"))
        row.addWidget(self.mix_label)
        self.mix_boxes, self.mix_sliders, self.mix_values = {}, {}, {}
        for key in obsrec.SOURCES:
            box = QCheckBox(_(SOURCE_LABELS[key]))
            box.setToolTip(_(SOURCE_TIPS[key]))
            sl = QSlider(Qt.Horizontal)
            sl.setRange(0, MIX_MAX)
            sl.setFixedWidth(80)
            sl.setToolTip(_("Lautstärke dieser Quelle im Clip (100 % = wie aufgenommen)."))
            val = QLabel("")
            val.setProperty("class", "dim")
            val.setMinimumWidth(38)
            self.mix_boxes[key], self.mix_sliders[key], self.mix_values[key] = box, sl, val
            row.addWidget(box)
            row.addWidget(sl)
            row.addWidget(val)
            row.addSpacing(8)
        self.mix_hint = QLabel(_("Eine Tonspur – zum Mischen nimmt OBS mit Spur 1–4 auf (Einstellungen → Mehr → Aufnahmen mit OBS)."))
        self.mix_hint.setProperty("class", "dim")
        self.mix_hint.setWordWrap(True)
        row.addWidget(self.mix_hint, 1)
        row.addStretch()
        self._mix_fill()
        for key in obsrec.SOURCES:
            self.mix_boxes[key].toggled.connect(self._mix_changed)
            self.mix_sliders[key].valueChanged.connect(lambda v, k=key: self._mix_slid(k))
            self.mix_sliders[key].sliderReleased.connect(self._mix_changed)
        return row

    def _mix_fill(self):
        """Controls for the sources the file has on their own tracks; none → only the hint. A source whose track
        is silent in the whole recording says so (1.8.18) – OBS recorded nothing there."""
        self.mix_hint.setVisible(not self._sources or bool(self._silent))
        if self._silent:
            names = ", ".join(_("{name} (Spur {n})", name=_(SOURCE_LABELS[k]), n=self._sources[k] + 1)
                              for k in obsrec.SOURCES if k in self._silent)
            self.mix_hint.setText(_("Still in dieser Aufnahme: {names} – OBS hat dort nichts aufgenommen. In OBS "
                                    "prüfen: Quelle in der Szene der Aufnahme, nicht stumm, Spur angehakt.",
                                    names=names))
        legacy = self._sources.get("discord") == obsrec.LEGACY
        for key in obsrec.SOURCES:
            box, sl, val = self.mix_boxes[key], self.mix_sliders[key], self.mix_values[key]
            have = key in self._sources
            for w in (box, sl, val):
                w.setVisible(bool(self._sources) and (w is box or not self.compact))   # compact: on/off only
                w.setEnabled(have)
            box.setChecked(have and self._mix_on[key])
            silent = key in self._silent
            if key in self._absent:                                # 1.8.23: nothing there to record
                box.setText(_("{name} – keine Quelle", name=_(SOURCE_LABELS[key])) if key == "other"
                            else _("{name} – in OBS aus", name=_(SOURCE_LABELS[key])))
                box.setToolTip(_(ABSENT_TIPS.get(key, ABSENT_TIPS["dbd"])))
            else:
                box.setText(_("{name} – still", name=_(SOURCE_LABELS[key])) if silent else _(SOURCE_LABELS[key]))
                box.setToolTip(_("Auf Spur {n} ist in der ganzen Aufnahme nichts zu hören.", n=self._sources[key] + 1)
                               if silent else _(SOURCE_TIPS[key]))
            sl.setValue(self._mix_vol[key] if have else 100)
            if legacy and key == "discord":                       # 1.8.5 file: Discord only on or off
                sl.setEnabled(False)
            val.setText(f"{sl.value()} %" if have else "")

    def _mix_slid(self, key):
        self.mix_values[key].setText(f"{self.mix_sliders[key].value()} %")
        if not self.mix_sliders[key].isSliderDown():              # keyboard / wheel: no release comes
            self._mix_changed()

    def mix(self):
        """{source: volume} for cut()/sound_wav() – None when the recording has no tracks to pick from."""
        if not self._sources:
            return None
        return {k: (self.mix_sliders[k].value() / 100.0 if self.mix_boxes[k].isChecked() else 0.0)
                for k in obsrec.SOURCES if k in self._sources}

    def _mix_changed(self, *_a):
        if not self._sources:
            return
        for key in obsrec.SOURCES:
            if key in self._sources:
                self._mix_on[key] = self.mix_boxes[key].isChecked()
                self._mix_vol[key] = self.mix_sliders[key].value()
        self._setting("clip_mix_on", dict(self._mix_on))
        self._setting("clip_mix_vol", dict(self._mix_vol))
        self._show_size()
        if self.playing and self.sound_box.isChecked() and os.name == "nt":   # hear the change at once
            back = self._play_to
            self._stop_player()
            self._play_to = back
            self.toggle_play()

    def _setting(self, key, value):
        if self.on_setting:
            self.on_setting(key, value)

    # ---- threads
    def _start_threads(self):
        b = self.bridge
        b.frame.connect(self._show_frame)
        b.played.connect(self._show_played)
        b.thumb.connect(self.timeline.set_thumb)
        b.thumb.connect(self._thumb_loaded)
        b.strip_done.connect(lambda: self._loaded("strip"))
        b.ended.connect(self._player_ended)
        b.saved.connect(self._saved)
        b.still.connect(self._still_saved)
        b.sound.connect(self._sound_ready)
        b.levels.connect(self._show_levels)
        threading.Thread(target=self._scrub_loop, name="clip-scrub", daemon=True).start()
        if any(i >= 0 for i in self._sources.values()):
            threading.Thread(target=self._level_loop, name="clip-levels", daemon=True).start()
        threading.Thread(target=self._thumb_loop, name="clip-thumbs", daemon=True).start()

    def _scrub_loop(self):
        while not self._closed:
            with self._scrub_lock:
                while self._want is None and not self._closed:
                    self._scrub_lock.wait(0.5)
                want, self._want = self._want, None
            if want is None:
                continue
            t, quick = want
            if quick:                                   # 1.8.3: the key frame at once (~40 ms), the exact frame after
                img = clipedit.frame_at(self.path, t, clipedit.PREVIEW_H, self.info, self.ffmpeg, keyframe=True)
                if img is not None and not self._closed:
                    self.bridge.frame.emit(t, img)
                with self._scrub_lock:
                    if self._want is not None:          # a newer wish meanwhile: that one, not this exact frame
                        continue
            img = clipedit.frame_at(self.path, t, clipedit.PREVIEW_H, self.info, self.ffmpeg)
            if img is not None and not self._closed:
                self.bridge.frame.emit(t, img)

    def _level_loop(self):
        levels = clipedit.track_levels(self.path, self.info.audio_tracks, self.ffmpeg)
        if levels and not self._closed:
            self.bridge.levels.emit(levels)

    def _show_levels(self, levels):
        """1.8.18: mark the sources whose own track is silent (a 1.8.5 file's Discord has no track of its own)."""
        silent = {k for k, i in self._sources.items()
                  if i >= 0 and levels.get(i) is not None and levels[i] <= clipedit.SILENT_DB}
        self._absent = {k for k in silent if self._recorded is not None and k not in self._recorded}
        self._silent = silent - self._absent
        if self._silent:
            log.info("Clip: stille Spuren in %s: %s", os.path.basename(self.path), ", ".join(sorted(self._silent)))
        self._mix_fill()

    def _thumb_loop(self):
        times = clipedit.thumb_times(self.info.duration, self.timeline.n_thumbs)
        got = set()                                  # 1.7.1: one ffmpeg run for the whole strip (key frames only)
        for i, img in clipedit.thumb_strip(self.path, times, clipedit.THUMB_H, self.info, self.ffmpeg,
                                           stop=lambda: self._closed):
            got.add(i)
            self.bridge.thumb.emit(i, img)
        for i, t in enumerate(times):                # whatever the run did not deliver: the old way
            if self._closed:
                return
            if i in got:
                continue
            img = clipedit.frame_at(self.path, t, clipedit.THUMB_H, self.info, self.ffmpeg)
            if img is not None and not self._closed:
                self.bridge.thumb.emit(i, img)
        if not self._closed:
            self.bridge.strip_done.emit()

    # ---- loading screen (1.8.3)
    def _thumb_loaded(self, _i, _img):
        self._load_state["thumbs"] += 1
        self._loaded(None)

    def _loaded(self, what):
        """A piece arrived (the first picture, the whole strip); the screen shows the count and goes when all is in."""
        if what:
            self._load_state[what] = True
        if self.loading is None or self.loading.finished:
            return
        st = self._load_state
        n = min(self.timeline.n_thumbs, st["thumbs"]) + (1 if st["frame"] else 0)
        self.loading.progress(n, _("{n} von {total} Bildern", n=n, total=self.timeline.n_thumbs + 1))
        if st["frame"] and st["strip"]:
            self.loading.finish()

    def resizeEvent(self, e):
        if self.loading is not None:
            self.loading.setGeometry(self.rect())
        super().resizeEvent(e)

    # ---- position
    def goto(self, t: float):
        """The playhead to ``t``: stops a playback, asks the scrub thread for the picture."""
        if self.playing:
            self._stop_player()
        t = min(max(0.0, float(t)), self.info.duration or 0.0)
        self.timeline.set_position(t)
        self._show_pos()
        with self._scrub_lock:
            self._want = (t, self._first_look)
            self._first_look = False
            self._scrub_lock.notify()

    def step(self, seconds: float):
        self.goto(self.timeline.pos + seconds)

    def step_frame(self, n: int):
        self.goto(self.timeline.pos + n / max(1.0, self.info.fps))

    def set_start(self):
        self.timeline.set_range(self.timeline.pos, max(self.timeline.end, self.timeline.pos + 0.1))
        self._show_range()

    def set_end(self):
        self.timeline.set_range(min(self.timeline.start, self.timeline.pos - 0.1), self.timeline.pos)
        self._show_range()

    def next_mark(self):
        later = [m for m in self.marks if m > self.timeline.pos + 0.05]
        if later or self.marks:
            self.goto(later[0] if later else self.marks[0])

    def _show_pos(self):
        self.pos_label.setText(f"{clipedit.fmt_pos(self.timeline.pos)} / {clipedit.fmt_pos(self.info.duration)}")

    def _show_range(self):
        tl = self.timeline
        self.range_label.setText(_("Clip: {start} – {end} ({length} s)", start=clipedit.fmt_pos(tl.start),
                                   end=clipedit.fmt_pos(tl.end), length=f"{tl.end - tl.start:.1f}"))
        self._show_size()
        if not self.name_edit.isModified() or not self.name_edit.text():
            self.name_edit.setText(clipedit.clip_name(self.path, tl.start, tl.end))
            self.name_edit.setModified(False)

    def _show_size(self):
        """1.6.1: what the chosen format makes of the clip – for Discord the picture size and frame rate."""
        tl, mode = self.timeline, self.mode_box.currentData() if hasattr(self, "mode_box") else "copy"
        secs = max(0.0, tl.end - tl.start)
        parts = []                                                 # 1.8.8: joined by " · ", no dot in front
        if mode == "discord":
            kbps, h, fps = clipedit.discord_plan(secs, self._target_mb, self.info)
            parts.append(_("wird {h}p {fps} fps, ≈ {kbps} kbit/s, unter {mb} MB",
                           h=h, fps=f"{fps:g}", kbps=kbps, mb=self._target_mb))
        elif self.info.ok and getattr(self.info, "duration", 0):
            try:
                size = os.path.getsize(self.path) * secs / self.info.duration
            except OSError:
                size = 0
            if size:
                parts.append(_("etwa {mb} MB", mb=f"{max(1.0, size / 1024 ** 2):.0f}"))
        if self._censor_args() and mode == "copy":                 # 1.7.2: boxes need the picture re-encoded
            parts.append(_("mit Zensur neu kodiert (wie „Genau“)"))
        if mode == "copy" and hasattr(self, "mix_boxes"):          # 1.8.6: a mix re-encodes only the sound
            flt, amap = obsrec.audio_graph(self.info.audio_tracks, self.mix())
            if flt or amap is None:
                parts.append(_("ohne Ton") if amap is None else _("Ton neu gemischt"))
        self.size_label.setText(" · ".join(parts))

    def _mode_changed(self, _i, save=True):
        mode = self.mode_box.currentData()
        self.target_box.setVisible(mode == "discord")
        if save:
            self._setting("clip_mode", mode)
        self._show_size()

    def _target_changed(self, _i):
        self._target_mb = int(self.target_box.currentData() or clipedit.DEFAULT_TARGET_MB)
        self._setting("clip_target_mb", self._target_mb)
        self._show_size()

    def watch_clip(self):
        """1.6.1: play the clip as it will be saved – from its start to its end, then back to its start."""
        tl = self.timeline
        self.goto(tl.start)
        self._play_to = tl.start
        self.toggle_play()

    def _show_frame(self, t, img):
        if not self.playing:
            self._paint(img)
        self._loaded("frame")

    def _show_played(self, t, img):
        if self.playing:
            self.timeline.set_position(t)
            self._show_pos()
            self._paint(img)

    def _paint(self, img):
        self.preview.set_frame(_qimage(img))

    # ---- playback
    def toggle_play(self):
        if self.playing:
            self._play_to = None
            self._stop_player()
            return
        start = self.timeline.pos
        end = self.timeline.end if start < self.timeline.end - 0.05 else self.info.duration
        self.playing = True
        self.play_btn.setText(_("⏸ Pause"))
        if self.sound_box.isChecked() and os.name == "nt":
            mix, n = self.mix(), self.info.audio_tracks
            threading.Thread(target=lambda: self.bridge.sound.emit(
                clipedit.sound_wav(self.path, start, end, self.ffmpeg, mix=mix, n_tracks=n), start),
                name="clip-sound", daemon=True).start()
        else:
            self._run_player(start, end)

    def _sound_ready(self, wav, start):
        if not self.playing or self.player is not None:
            if wav:
                self._drop_wav(wav)
            return
        self._wav = wav
        if wav:
            try:
                import winsound
                winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            except Exception:                                   # no sound device: the picture still plays
                pass
        self._run_player(start, self.timeline.end if start < self.timeline.end - 0.05 else self.info.duration)

    def _run_player(self, start, end):
        b = self.bridge
        self.player = clipedit.FramePlayer(self.path, start, self.info, lambda t, img: b.played.emit(t, img),
                                           lambda: b.ended.emit(self.player), end=end, ffmpeg=self.ffmpeg)
        self.player.start()

    def _stop_player(self):
        self.playing = False
        self.play_btn.setText(_("▶ Abspielen"))
        pl, self.player = self.player, None
        if pl is not None:
            pl.stop()
        if os.name == "nt":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        if self._wav:
            self._drop_wav(self._wav)
            self._wav = None

    @staticmethod
    def _drop_wav(path):
        try:
            os.remove(path)
        except OSError:
            pass

    def _player_ended(self, player):
        if player is self.player and self.playing:            # ran to the end (not stopped by us)
            self._stop_player()
            back, self._play_to = self._play_to, None
            self.goto(back if back is not None else self.timeline.pos)

    # ---- saving
    def save(self):
        tl = self.timeline
        name = clipedit.NAME_CHARS.sub("", self.name_edit.text()).strip() or clipedit.clip_name(self.path, tl.start, tl.end)
        mode = self.mode_box.currentData() or "copy"
        try:
            os.makedirs(self.clips_dir, exist_ok=True)
        except OSError as e:
            self.status.setText(_("Clips-Ordner nicht anlegbar: {error}", error=e))
            return
        out = clipedit.unique_path(self.clips_dir, name, ".mp4")
        self.save_btn.setEnabled(False)
        self.status.setText(_("Schreibe {file} …", file=os.path.basename(out)))
        start, end = tl.start, tl.end
        self.saved_seconds[out] = round(max(0.0, end - start), 1)

        target, info, mix = self._target_mb, self.info, self.mix()
        censor = self._censor_args()
        if mode != "copy" or censor:
            self.status.setText(_("Kodiere {file} … (dauert etwas)", file=os.path.basename(out)))

        def work():
            ok, why = clipedit.cut(self.path, start, end, out, mode, self.ffmpeg, target_mb=target, info=info,
                                   mix=mix, **censor)
            self.bridge.saved.emit(ok, out, why)
        threading.Thread(target=work, name="clip-save", daemon=True).start()

    def _timeline_pick(self, ident, t):
        """1.8.10: the right-click menu of the strip."""
        tl = self.timeline
        if ident == "seek":
            self.goto(t)
        elif ident == "start" and t < tl.end - 0.1:
            tl.set_range(t, tl.end)
            self._show_range()
            self.goto(t)
        elif ident == "end" and t > tl.start + 0.1:
            tl.set_range(tl.start, t)
            self._show_range()
        elif ident == "still":
            self.save_still(t)

    def save_still(self, t):
        """1.8.10: the picture at ``t`` in full size as PNG next to the clips (Clips/<round> – Bild m:ss.png)."""
        if not self.info.ok or not self.ffmpeg:
            return
        name = clipedit.NAME_CHARS.sub("", "{} – {} {}".format(
            os.path.splitext(os.path.basename(self.path))[0], _("Bild"), clipedit.fmt_pos(t).replace(":", "-")))
        try:
            os.makedirs(self.clips_dir, exist_ok=True)
        except OSError as e:
            self.status.setText(_("Clips-Ordner nicht anlegbar: {error}", error=e))
            return
        out = clipedit.unique_path(self.clips_dir, name, ".png")
        path, info, ffmpeg, b = self.path, self.info, self.ffmpeg, self.bridge

        def work():
            img = clipedit.frame_at(path, t, info.height, info, ffmpeg)
            ok = False
            if img is not None:
                try:
                    img.save(out)
                    ok = True
                except OSError:
                    pass
            b.still.emit(ok, out)
        threading.Thread(target=work, name="clip-still", daemon=True).start()

    def _still_saved(self, ok, out):
        if ok:
            self._last_out = out
            self.show_btn.setEnabled(True)
            self.status.setText(_("Standbild gespeichert: {file}", file=os.path.basename(out)))
            self.log(_("Standbild gespeichert: {file}", file=out), "System")
            if self.on_saved:                       # 1.8.13: stills are in the clips list too
                self.on_saved(out)
        else:
            self.status.setText(_("Standbild nicht gespeichert."))

    def _saved(self, ok, out, why):
        self.save_btn.setEnabled(True)
        if ok:
            self._last_out = out
            self.show_btn.setEnabled(True)
            try:
                mb = os.path.getsize(out) / 1024 ** 2
            except OSError:
                mb = 0.0
            self.status.setText(_("Gespeichert: {file} ({mb} MB)", file=os.path.basename(out), mb=f"{mb:.1f}"))
            self.log(_("Clip gespeichert: {file}", file=out), "System")
            if self.on_saved:
                self.on_saved(out)
        else:
            self.status.setText(_("Clip nicht gespeichert: {why}", why=why or "ffmpeg"))
            self.log(_("Clip nicht gespeichert: {why}", why=why or "ffmpeg"), "Fehler")

    def _show_saved(self):
        if not self._last_out:
            return
        if os.name == "nt":
            import subprocess
            subprocess.Popen(["explorer", "/select,", os.path.normpath(self._last_out)])   # noqa: S603,S607
        else:
            self.status.setText(self._last_out)

    def _open_clips(self):
        try:
            os.makedirs(self.clips_dir, exist_ok=True)
            if os.name == "nt":
                os.startfile(self.clips_dir)                     # noqa: S606 – opens Explorer
            else:
                self.status.setText(self.clips_dir)
        except OSError as e:
            self.status.setText(str(e))

    # ---- keys / closing
    def keyPressEvent(self, e):
        k, mods = e.key(), e.modifiers()
        big, frame = bool(mods & Qt.ShiftModifier), bool(mods & Qt.ControlModifier)
        if k == Qt.Key_Space:
            self.toggle_play()
        elif k == Qt.Key_Left:
            self.step_frame(-1) if frame else self.step(-(STEP_BIG if big else STEP_SMALL))
        elif k == Qt.Key_Right:
            self.step_frame(1) if frame else self.step(STEP_BIG if big else STEP_SMALL)
        elif k == Qt.Key_I:
            self.set_start()
        elif k == Qt.Key_O:
            self.set_end()
        elif k == Qt.Key_M:
            self.next_mark()
        elif k == Qt.Key_Home:
            self.goto(0.0)
        elif k == Qt.Key_End:
            self.goto(self.info.duration)
        elif k in (Qt.Key_Delete, Qt.Key_Backspace) and self.preview.editing:
            self.preview.remove_selected()
        elif k == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    def closeEvent(self, e):
        self._closed = True
        self._stop_player()
        with self._scrub_lock:
            self._scrub_lock.notify_all()
        super().closeEvent(e)
