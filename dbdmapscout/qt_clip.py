"""The clip editor window (1.5.1, user's wish: cut rounds "wie in Medal"): a preview picture, a timeline with
thumbnails, the F8 marks, a start/end range and a playhead; play/pause (frames streamed by ffmpeg, the sound
by Windows from a WAV of the same stretch), 1-s / 5-s / frame steps, "Clip speichern" (stream copy or frame
exact, see clipedit.cut) into the folder "Clips" next to the recordings.

All ffmpeg work runs in threads (clipedit); results come back over Qt signals. The window is a plain top-level
QWidget the App opens from the tab "Aufnahmen" (app_recordings._rec_clip)."""
from __future__ import annotations

import os
import threading

from PySide6.QtCore import QObject, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from . import clipedit, qt_theme
from .i18n import N_, _

MODE_LABELS = {"copy": N_("Schnell (an Schlüsselbildern, Anfang bis zu ein paar Sekunden früher)"),
               "exact": N_("Genau (Bild neu kodiert, dauert etwas)"),
               "discord": N_("Für Discord (passt unter die Zielgrösse)")}
KEY_HINT = N_("Leertaste Abspielen · ←/→ 1 s · Shift 5 s · Strg 1 Bild · I/O Start/Ende · M Marke · "
              "Pos1/Ende Anfang/Schluss · Esc schliessen")
STEP_SMALL, STEP_BIG = 1.0, 5.0
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


class Timeline(QWidget):
    """Thumbnail strip with the start/end range, the playhead and the marks. Drag the handles or the playhead,
    click to seek, wheel = ±1 s (Ctrl: ±0.1 s)."""
    HANDLE = 7
    TOP = 12
    changed = Signal()                    # start/end moved
    seek = Signal(float)                  # the user wants this moment

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


class ClipWindow(QWidget):
    """One editor per recording. ``on_saved(path)`` / ``on_setting(key, value)`` / ``log(text, kind)`` come from
    the App; ``mode``/``sound`` are the remembered settings."""

    def __init__(self, path: str, marks: list, clips_dir: str, mode: str = "copy", sound: bool = True,
                 on_saved=None, on_setting=None, log=None, dark=True, qss: str = "", title: str = "",
                 target_mb: int = clipedit.DEFAULT_TARGET_MB):
        super().__init__(None, Qt.Window)
        self.path, self.marks, self.clips_dir = path, sorted(float(m) for m in marks or ()), clips_dir
        self.on_saved, self.on_setting, self.log = on_saved, on_setting, (log or (lambda text, kind="System": None))
        self.dark = dark
        self.info = clipedit.probe(path)
        self.ffmpeg = clipedit.ffmpeg_exe()
        self.bridge = _Bridge()
        self.player = None
        self.playing = False
        self._wav = None
        self._want = None                   # latest scrub moment asked for
        self._scrub_lock = threading.Condition()
        self._closed = False
        self._target_mb = int(target_mb) if target_mb in clipedit.TARGETS_MB else clipedit.DEFAULT_TARGET_MB
        self._last_out = None               # 1.6.1: the clip saved last (Explorer button)
        self._play_to = None                # 1.6.1: "Clip ansehen" plays start..end, then back to the start
        self.setObjectName("page")
        self.setWindowTitle(title or _("Clip schneiden – {name}", name=os.path.basename(path)))
        if qss:
            self.setStyleSheet(qss)
        self._build(mode, sound)
        self.resize(1100, 780)
        self.setMinimumSize(760, 600)
        self.setFocusPolicy(Qt.StrongFocus)
        if not self.info.ok or not self.ffmpeg:
            self.status.setText(_("Datei nicht lesbar oder ffmpeg fehlt – keine Vorschau."))
            self.save_btn.setEnabled(False)
            return
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
        lay.setSpacing(8)
        self.preview = QLabel()
        self.preview.setMinimumSize(*PREVIEW_MIN)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background: #000; border-radius: 6px;")
        lay.addWidget(self.preview, 1)
        self.timeline = Timeline(self.dark)
        self.timeline.seek.connect(self.goto)
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
        self._btn(row, _("Start setzen"), self.set_start, _("Der Clip beginnt am Abspielkopf (Taste I)."))
        self._btn(row, _("Ende setzen"), self.set_end, _("Der Clip endet am Abspielkopf (Taste O)."))
        self.mark_btn = self._btn(row, _("Zur Marke ▸"), self.next_mark, _("Springt zur nächsten F8-Marke (Taste M)."))
        self.mark_btn.setEnabled(bool(self.marks))
        lay.addLayout(row)

        # the clip: from – to, length, size estimate; "Clip ansehen" plays exactly that
        crow = QHBoxLayout()
        self.range_label = QLabel("")
        self.range_label.setProperty("class", "big")
        crow.addWidget(self.range_label)
        self.size_label = QLabel("")
        self.size_label.setProperty("class", "dim")
        crow.addWidget(self.size_label)
        crow.addStretch()
        self.watch_btn = self._btn(crow, _("▶ Clip ansehen"), self.watch_clip,
                                   _("Spielt genau den Ausschnitt ab und springt danach an seinen Anfang zurück."))
        lay.addLayout(crow)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setProperty("class", "sep")
        lay.addWidget(sep)

        # export: name, format, target size, sound
        row2 = QHBoxLayout()
        row2.addWidget(QLabel(_("Name")))
        self.name_edit = QLineEdit()
        row2.addWidget(self.name_edit, 1)
        row2.addWidget(QLabel(_("Format")))
        self.mode_box = QComboBox()
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
        lay.addLayout(row2)

        row3 = QHBoxLayout()
        self.save_btn = self._btn(row3, _("Clip speichern"), self.save, _("Schreibt den Ausschnitt als MP4 in den Ordner „Clips“ neben den Aufnahmen."))
        self.save_btn.setObjectName("primary")
        self.show_btn = self._btn(row3, _("Im Explorer zeigen"), self._show_saved, _("Zeigt den zuletzt gespeicherten Clip im Explorer."))
        self.show_btn.setEnabled(False)
        self.open_btn = self._btn(row3, _("Clips-Ordner öffnen"), self._open_clips, _("Öffnet den Ordner „Clips“ im Explorer."))
        self.status = QLabel("")
        self.status.setProperty("class", "dim")
        self.status.setWordWrap(True)
        row3.addWidget(self.status, 1)
        lay.addLayout(row3)
        hint = QLabel(_(KEY_HINT))
        hint.setProperty("class", "dim")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self._mode_changed(self.mode_box.currentIndex(), save=False)

    def _btn(self, row, text, slot, tip=""):
        b = QPushButton(text)
        b.setFocusPolicy(Qt.NoFocus)                      # the keys stay with the window
        b.clicked.connect(slot)
        if tip:
            b.setToolTip(tip)
        row.addWidget(b)
        return b

    def _setting(self, key, value):
        if self.on_setting:
            self.on_setting(key, value)

    # ---- threads
    def _start_threads(self):
        b = self.bridge
        b.frame.connect(self._show_frame)
        b.played.connect(self._show_played)
        b.thumb.connect(self.timeline.set_thumb)
        b.ended.connect(self._player_ended)
        b.saved.connect(self._saved)
        b.sound.connect(self._sound_ready)
        threading.Thread(target=self._scrub_loop, name="clip-scrub", daemon=True).start()
        threading.Thread(target=self._thumb_loop, name="clip-thumbs", daemon=True).start()

    def _scrub_loop(self):
        while not self._closed:
            with self._scrub_lock:
                while self._want is None and not self._closed:
                    self._scrub_lock.wait(0.5)
                t, self._want = self._want, None
            if t is None:
                continue
            img = clipedit.frame_at(self.path, t, clipedit.PREVIEW_H, self.info, self.ffmpeg)
            if img is not None and not self._closed:
                self.bridge.frame.emit(t, img)

    def _thumb_loop(self):
        for i, t in enumerate(clipedit.thumb_times(self.info.duration, self.timeline.n_thumbs)):
            if self._closed:
                return
            img = clipedit.frame_at(self.path, t, clipedit.THUMB_H, self.info, self.ffmpeg)
            if img is not None and not self._closed:
                self.bridge.thumb.emit(i, img)

    # ---- position
    def goto(self, t: float):
        """The playhead to ``t``: stops a playback, asks the scrub thread for the picture."""
        if self.playing:
            self._stop_player()
        t = min(max(0.0, float(t)), self.info.duration or 0.0)
        self.timeline.set_position(t)
        self._show_pos()
        with self._scrub_lock:
            self._want = t
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
        if mode == "discord":
            kbps, h, fps = clipedit.discord_plan(secs, self._target_mb, self.info)
            self.size_label.setText(_("· wird {h}p {fps} fps, ≈ {kbps} kbit/s, unter {mb} MB",
                                      h=h, fps=f"{fps:g}", kbps=kbps, mb=self._target_mb))
        elif self.info.ok and getattr(self.info, "duration", 0):
            try:
                size = os.path.getsize(self.path) * secs / self.info.duration
            except OSError:
                size = 0
            self.size_label.setText(_("· etwa {mb} MB", mb=f"{size / 1024 ** 2:.0f}") if size else "")
        else:
            self.size_label.setText("")

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

    def _show_played(self, t, img):
        if self.playing:
            self.timeline.set_position(t)
            self._show_pos()
            self._paint(img)

    def _paint(self, img):
        pm = QPixmap.fromImage(_qimage(img))
        self._last_pm = pm
        self.preview.setPixmap(pm.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, e):
        pm = getattr(self, "_last_pm", None)
        if pm is not None:
            self.preview.setPixmap(pm.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        super().resizeEvent(e)

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
            threading.Thread(target=lambda: self.bridge.sound.emit(clipedit.sound_wav(self.path, start, end, self.ffmpeg), start),
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

        target, info = self._target_mb, self.info
        if mode != "copy":
            self.status.setText(_("Kodiere {file} … (dauert etwas)", file=os.path.basename(out)))

        def work():
            ok, why = clipedit.cut(self.path, start, end, out, mode, self.ffmpeg, target_mb=target, info=info)
            self.bridge.saved.emit(ok, out, why)
        threading.Thread(target=work, name="clip-save", daemon=True).start()

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
