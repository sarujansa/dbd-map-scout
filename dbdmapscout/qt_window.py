"""The control window (Qt): navigation on the left, one page per area.

The window only shows and reports: every button calls ``post`` (→ App.events, handled in App._poll, in order
with the detection's events), and the App pushes its state from its own ticks (``show_model``, ``show_states``).
The pages draw the App's UI model (uimodel.py; app_qt.ui_state). No modal dialogs: ``exec()`` would run a second
event loop inside a click.
"""
from __future__ import annotations

import base64
import html
import sys

from PIL import Image
from PySide6.QtCore import QByteArray, QEvent, QSize, Qt
from PySide6.QtGui import QColor, QFontDatabase, QIcon, QImage, QPalette, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QPlainTextEdit, QProgressBar,
                               QPushButton, QRadioButton,
                               QScrollArea, QSizePolicy, QSlider, QStackedWidget, QTabWidget, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from . import qt_theme
from .i18n import N_, _
from .mapimage import FONT as FIRA

# key, label (the navigation's icons are drawn by nav_icon: same size and place for all)
PAGES = (("overview", N_("Übersicht")), ("maps", "Maps"), ("overlay", N_("Overlay")), ("stats", N_("Statistik")),
         ("server", N_("Server")), ("settings", N_("Einstellungen")), ("detect", N_("Erkennung")), ("log", "Log"))
NAV_ICON = 18                     # px (logical): every icon of the navigation in the same box
AUTO_PAGES = ("stats", "server", "detect", "log")   # built from the tab's structure (app_qt.ui_layout)
THUMB_H = 170                     # px (logical) of the map picture on the overview
SLIDER_MAX = 420                  # px (logical): longest slider (overlay position, size, opacity)

# Hand-made pages: every key names a widget of the UI model registered with App._reg; texts, values,
# enabled/shown come from it (App._qt_refresh → show_states), a click is done on it (post("act", (key, value))).
# ("card", frame key, rows) – a row is one control or ("row", [controls]); controls: ("check"|"button"|"combo"|
# "slider"|"label"|"hint", key), ("stretch",).
SPECS = {
    "overlay": (
        ("card", "ov.pos", (
            ("row", (("label", "ov.anchor.label"), ("combo", "ov.anchor"), ("stretch",), ("button", "ov.reset"))),
            ("slider", "ov.posx"), ("slider", "ov.posy"),
            ("row", (("button", "ov.edit"), ("button", "ov.test"), ("stretch",))),
            ("hint", "ov.pos_hint"), ("check", "ov.keep_bar"))),
        ("card", "ov.look", (
            ("slider", "ov.size"),
            ("row", (("hint", "ov.map_size"), ("stretch",), ("button", "ov.map_size_reset"))),
            ("slider", "ov.opacity"),
            ("check", "ov.show_map"), ("check", "ov.focus"), ("check", "ov.caption"), ("check", "ov.timer"),
            ("check", "ov.server"), ("check", "ov.waiting"), ("check", "ov.floors"), ("check", "ov.record"),
            ("check", "ov.transparent"))),
        ("card", "ov.sys", (
            ("row", (("label", "ov.sysinfo.label"), ("combo", "ov.sysinfo"), ("stretch",))),
            ("hint", "ov.sys_text"), ("hint", "ov.sys_hint"))),
    ),
    "settings": (
        ("card", "st.look", (
            ("row", (("label", "st.lang.label"), ("combo", "st.lang"), ("stretch",))), ("hint", "st.lang_note"),
            ("check", "st.dark"),
            ("row", (("label", "st.zoom.label"), ("combo", "st.zoom"), ("stretch",))))),
        ("card", "st.notify", (
            ("check", "st.lobby_notify"), ("check", "st.lobby_remind"), ("check", "st.notify_background_only"),
            ("hint", "st.notify_text"), ("row", (("button", "st.notify_test"), ("stretch",))))),
        ("card", "st.start", (("check", "st.tray"), ("check", "st.autostart"), ("hint", "st.autostart_info"))),
        ("card", "st.hotkeys", (
            ("grid", 2, tuple(("row", (("label", f"st.hk.{k}.label"), ("stretch",), ("hotkey", f"st.hk.{k}")))
                              for k in ("toggle_overlay", "next_variant", "scan_now", "prev_map", "next_map",
                                        "bigger", "smaller", "edit_position", "rotate_map", "next_floor",
                                        "reject_map"))),
            ("row", (("button", "st.hk_defaults"), ("hint", "st.hk_status"))))),
        ("card", "st.updates", (
            ("check", "st.update"), ("hint", "st.update_note"),
            ("row", (("button", "st.upd_btn"), ("button", "st.upd_apply"), ("stretch",))), ("hint", "st.upd_status"))),
        ("row", (("button", "st.more_btn"), ("stretch",))),
        ("card", "st.more.own", (("row", (("hint", "st.more.aliases"), ("button", "st.more.aliases_clear"))),)),
        ("card", "st.more.official", (("check", "st.more.off_open"), ("check", "st.more.off_notify"),
                                      ("row", (("button", "st.more.script"), ("stretch",))), ("hint", "st.more.off_text"))),
        ("card", "st.more.backup", (("row", (("button", "st.more.export"), ("button", "st.more.import"), ("stretch",))),)),
        ("card", "st.more.folders", (("row", (("button", "st.more.dir"), ("button", "st.more.maps_dir"), ("stretch",))),)),
        ("plain", "st.version"),
    ),
}


def _spec_keys(items):
    for it in items:
        kind = it[0]
        if kind == "card":
            yield it[1]
            yield from _spec_keys(it[2])
        elif kind == "row":
            yield from _spec_keys(it[1])
        elif kind == "grid":
            yield from _spec_keys(it[2])
        elif kind in ("check", "button", "combo", "slider", "label", "hint", "value", "plain", "hotkey"):
            yield it[1]


def page_keys(page: str | None = None) -> set:
    """Widget keys a hand-made page shows (all pages without ``page``) – also the whitelist for its clicks."""
    pages = [page] if page else list(SPECS)
    return {k for p in pages for k in _spec_keys(SPECS.get(p, ()))}


def application() -> QApplication:
    """The one QApplication of the process (main thread, before any widget)."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
        app.setStyle("Fusion")
        app.setQuitOnLastWindowClosed(False)          # closing goes through the App (quit / tray)
        QFontDatabase.addApplicationFont(FIRA)         # map names like on the map pictures
    return app


def pixmap_from_pil(img: Image.Image, height: int, ratio: float = 1.0) -> QPixmap:
    """Map picture (PIL, RGBA) -> QPixmap ``height`` logical px tall, sharp on scaled screens."""
    img = img.convert("RGBA")
    h = max(1, round(height * ratio))
    w = max(1, round(img.width * h / img.height))
    img = img.resize((w, h), Image.LANCZOS)
    data = img.tobytes("raw", "RGBA")
    pm = QPixmap.fromImage(QImage(data, w, h, 4 * w, QImage.Format_RGBA8888).copy())
    pm.setDevicePixelRatio(ratio)
    return pm


def _label(text="", cls=None, wrap=False):
    w = QLabel(text)
    if cls:
        w.setProperty("class", cls)
    if wrap:
        w.setWordWrap(True)
    return w


def _tip(label: str) -> str:
    """Hover text of a button of the window itself (tooltip.TIPS, by German label)."""
    from .tooltip import tip_for_label
    return tip_for_label(_(label)) or ""


def _card():
    f = QFrame()
    f.setProperty("class", "card")
    return f


def _set(widget, text):
    if widget.text() != text:
        widget.setText(text)


class FactBox(QWidget):
    """Title, big value, optional bar and a small line (map card values and today's tiles)."""

    def __init__(self, bar=False):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.title = _label(cls="dim")
        self.value = _label(cls="kpi")
        lay.addWidget(self.title)
        lay.addWidget(self.value)
        self.bar = None
        if bar:
            self.bar = QProgressBar()
            self.bar.setTextVisible(False)
            self.bar.setRange(0, 1000)
            lay.addWidget(self.bar)
        self.sub = _label(cls="dim")
        lay.addWidget(self.sub)
        self._colour = None

    def show_fact(self, f):
        _set(self.title, f.title)
        _set(self.value, f.value)
        _set(self.sub, f.sub)
        colour = qt_theme.hex_colour(f.colour) if f.colour is not None else None
        if colour != self._colour:
            self._colour = colour
            self.value.setStyleSheet(f"color: {colour};" if colour else "")
        if self.bar is not None:
            self.bar.setVisible(f.frac is not None)
            self.bar.setValue(round(1000 * min(1.0, max(0.0, f.frac or 0.0))))


class OverviewPage(QWidget):
    def __init__(self, post):
        super().__init__()
        self.setObjectName("page")
        self._post = post
        self._thumb_rev = None
        self._pill_style = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("page")
        scroll.setWidget(body)
        page = QVBoxLayout(body)
        page.setContentsMargins(22, 18, 22, 18)
        page.setSpacing(14)

        top = QHBoxLayout()
        top.addWidget(_label(_("Übersicht"), "h1"))
        top.addStretch()
        self.pill = QLabel()
        self.pill.setObjectName("pill")
        self.pill.setMaximumWidth(520)
        top.addWidget(self.pill, alignment=Qt.AlignVCenter)
        page.addLayout(top)

        # first start only: what to do and the hotkeys that matter
        self.welcome = _card()
        wl = QHBoxLayout(self.welcome)
        wl.setContentsMargins(14, 10, 14, 10)
        self.welcome_text = _label(wrap=True)
        wl.addWidget(self.welcome_text, 1)
        b = QPushButton(_("Verstanden"))
        b.clicked.connect(lambda: self._post("welcome"))
        wl.addWidget(b, alignment=Qt.AlignVCenter)
        page.addWidget(self.welcome)

        # the map on display: picture, name, values, actions
        card = _card()
        cl = QHBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(18)
        self.thumb = QLabel()
        self.thumb.setObjectName("thumb")
        self.thumb.setFixedSize(THUMB_H + 12, THUMB_H + 12)
        self.thumb.setAlignment(Qt.AlignCenter)
        cl.addWidget(self.thumb, alignment=Qt.AlignTop)
        info = QVBoxLayout()
        info.setSpacing(4)
        info.addWidget(_label(_("Aktuelle Map").upper(), "h2"))
        self.map_name = _label(cls="map", wrap=True)
        info.addWidget(self.map_name)
        self.map_line = _label(cls="dim", wrap=True)
        info.addWidget(self.map_line)
        self.queue = _label(cls="dim", wrap=True)
        info.addWidget(self.queue)
        info.addSpacing(8)
        grid = QGridLayout()
        grid.setHorizontalSpacing(26)
        self.facts = [FactBox() for _i in range(4)]
        for i, box in enumerate(self.facts):
            grid.addWidget(box, 0, i)
        info.addLayout(grid)
        self.note = _label(cls="note", wrap=True)
        info.addWidget(self.note)
        self.unknown = QWidget()
        ul = QHBoxLayout(self.unknown)
        ul.setContentsMargins(0, 0, 0, 0)
        self.unknown_text = _label(cls="note", wrap=True)
        ul.addWidget(self.unknown_text, 1)
        for text, action in ((N_("Zuordnen …"), "assign"), (N_("Bild hinzufügen …"), "picture"),
                             ("✕", "dismiss_unknown")):
            ub = QPushButton(_(text))
            ub.setToolTip(_tip(text))
            ub.clicked.connect(lambda _c=False, a=action: self._post(a))
            ul.addWidget(ub)
        info.addWidget(self.unknown)
        info.addStretch()
        btns = QHBoxLayout()
        btns.setSpacing(6)
        self.buttons = {}
        for key in ("scan", "rotate", "toggle", "reject", "confirm", "layout", "floor"):
            b = QPushButton()
            if key == "scan":
                b.setObjectName("primary")
            b.clicked.connect(lambda _c=False, k=key: self._post(k))
            btns.addWidget(b)
            self.buttons[key] = b
        btns.addStretch()
        info.addLayout(btns)
        cl.addLayout(info, 1)
        page.addWidget(card)

        # today
        head = QHBoxLayout()
        head.addWidget(_label(_("Heute").upper(), "h2"))
        head.addStretch()
        self.today_note = _label(cls="dim")
        head.addWidget(self.today_note)
        page.addLayout(head)
        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.tiles = []
        for _i in range(4):
            t = _card()
            tl = QVBoxLayout(t)
            tl.setContentsMargins(14, 12, 14, 12)
            box = FactBox(bar=True)
            tl.addWidget(box)
            tiles.addWidget(t, 1)
            self.tiles.append(box)
        page.addLayout(tiles)

        # system values and the last rounds
        row = QHBoxLayout()
        row.setSpacing(12)
        sysc = _card()
        self.sys_lay = QVBoxLayout(sysc)
        self.sys_lay.setContentsMargins(14, 12, 14, 12)
        self.sys_lay.addWidget(_label(_("System").upper(), "h2"))
        self.sys_rows = []
        self.sys_note = _label(cls="dim", wrap=True)
        self.sys_lay.addWidget(self.sys_note)
        self.sys_lay.addStretch()
        row.addWidget(sysc, 1)
        last = _card()
        self.last_lay = QVBoxLayout(last)
        self.last_lay.setContentsMargins(14, 12, 14, 12)
        self.last_lay.addWidget(_label(_("Letzte Runden").upper(), "h2"))
        self.last_rows = []
        self.last_empty = _label(_("Noch keine Runden gespeichert."), "dim")
        self.last_lay.addWidget(self.last_empty)
        self.last_lay.addStretch()
        row.addWidget(last, 1)
        page.addLayout(row)
        page.addStretch()

    # ------------------------------------------------------------- update
    def update_page(self, o, thumb=None, tips=None):
        _set(self.pill, "●  " + o.status_text)
        pill = qt_theme.pill_style(o.status_kind)
        if pill != self._pill_style:                  # re-styling repaints: only on a change
            self._pill_style = pill
            self.pill.setStyleSheet(pill)
        self.welcome.setVisible(bool(o.welcome))
        _set(self.welcome_text, o.welcome)
        _set(self.map_name, o.map_label or _("Noch keine Map"))
        _set(self.map_line, o.map_line)
        _set(self.queue, o.queue)
        self.queue.setVisible(bool(o.queue))
        if o.thumb_rev != self._thumb_rev:
            self._thumb_rev = o.thumb_rev
            if thumb is None:
                self.thumb.clear()
            else:
                h = THUMB_H if thumb.height >= thumb.width else round(THUMB_H * thumb.height / thumb.width)
                self.thumb.setPixmap(pixmap_from_pil(thumb, max(1, h), self.devicePixelRatioF()))   # fits both ways
        for box, f in zip(self.facts, o.facts):
            box.show_fact(f)
        _set(self.note, o.note)
        self.note.setVisible(bool(o.note))
        _set(self.unknown_text, o.unknown)
        self.unknown.setVisible(bool(o.unknown))
        for key, b in self.buttons.items():
            a = o.actions.get(key)
            b.setVisible(a is not None)
            if a is not None:
                _set(b, a[1])
                b.setEnabled(a[0])
                if tips:
                    tip = tips(key, a[1]) or ""
                    if b.toolTip() != tip:
                        b.setToolTip(tip)
        _set(self.today_note, o.today_note)
        for box, f in zip(self.tiles, o.today):
            box.show_fact(f)
        self._show_system(o)
        self._show_rounds(o.rounds)

    def _show_system(self, o):
        while len(self.sys_rows) < len(o.system):
            r = QHBoxLayout()
            name, value = _label(cls="dim"), _label()
            r.addWidget(name)
            r.addStretch()
            r.addWidget(value)
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setRange(0, 1000)
            pos = 1 + 2 * len(self.sys_rows)
            self.sys_lay.insertLayout(pos, r)
            self.sys_lay.insertWidget(pos + 1, bar)
            self.sys_rows.append((name, value, bar, [None]))
        for i, (name, value, bar, colour) in enumerate(self.sys_rows):
            shown = i < len(o.system)
            for w in (name, value):
                w.setVisible(shown)
            if not shown:
                bar.setVisible(False)
                continue
            label, text, frac, col = o.system[i]
            _set(name, label)
            _set(value, text)
            bar.setVisible(frac is not None)
            bar.setValue(round(1000 * min(1.0, max(0.0, frac or 0.0))))
            want = qt_theme.bar_style(col) if col is not None else ""
            if want != colour[0]:
                colour[0] = want
                bar.setStyleSheet(want)
        _set(self.sys_note, o.system_note)
        self.sys_note.setVisible(bool(o.system_note))

    def _show_rounds(self, rounds):
        while len(self.last_rows) < len(rounds):
            r = QHBoxLayout()
            left, right = _label(), _label(cls="dim")
            left.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)      # long names must not widen it
            r.addWidget(left, 1)
            r.addWidget(right)
            self.last_lay.insertLayout(1 + len(self.last_rows), r)
            self.last_rows.append((left, right))
        for i, (left, right) in enumerate(self.last_rows):
            shown = i < len(rounds)
            left.setVisible(shown)
            right.setVisible(shown)
            if shown:
                _set(left, rounds[i][0])
                _set(right, rounds[i][1])
        self.last_empty.setVisible(not rounds)


def _scroll_page(title, scroll=True):
    """(page, body layout): a page that scrolls as a whole, with its title on top (``scroll`` False: a page that
    fits the window, its parts scroll on their own)."""
    page = QWidget()
    page.setObjectName("page")
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    body = QWidget()
    body.setObjectName("page")
    if scroll:
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        outer.addWidget(sa)
        sa.setWidget(body)
    else:
        outer.addWidget(body)
    lay = QVBoxLayout(body)
    lay.setContentsMargins(22, 18, 22, 18)
    lay.setSpacing(12)
    lay.addWidget(_label(title, "h1"))
    return page, lay


def make_control(kind, key, post):
    """(widget, extra) of one control of the UI model; clicks go out as post("act", (key, value))."""
    extra = None
    if kind == "check":
        w = QCheckBox()
        w.clicked.connect(lambda checked: post("act", (key, checked)))
    elif kind == "button":
        w = QPushButton()
        w.clicked.connect(lambda _c=False: post("act", (key, None)))
    elif kind == "combo":
        w = QComboBox()
        w.setMinimumWidth(140)
        w.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        w.activated.connect(lambda i: post("act", (key, w.itemText(i))))
        w.editTextChanged.connect(lambda text: w.isEditable() and w.hasFocus() and post("act", (key, text)))
    elif kind == "slider":
        w = QWidget()
        r = QHBoxLayout(w)
        r.setContentsMargins(0, 0, 0, 0)
        name, value = _label(), _label()
        name.setMinimumWidth(110)
        value.setMinimumWidth(56)
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        s = QSlider(Qt.Horizontal)
        s.setMaximumWidth(SLIDER_MAX)              # a wide window: no slider across the whole page
        s.valueChanged.connect(lambda v: post("act", (key, v)))
        r.addWidget(name)
        r.addWidget(s, 1)
        r.addWidget(value)
        r.addStretch()
        extra = (name, s, value)
    elif kind == "table":
        w = Table(key, post)
    elif kind == "chart":
        w = Chart()
    elif kind == "dashboard":
        w = DashboardView()
    elif kind == "log":
        w = LogView()
    elif kind == "radio":
        w = QRadioButton()
        w.setAutoExclusive(False)                 # the model decides which one is on
        w.clicked.connect(lambda _c=False: post("act", (key, None)))
    elif kind == "entry":
        w = QLineEdit()
        w.setMinimumWidth(220)
        w.textEdited.connect(lambda text: post("act", (key, text)))
    elif kind == "image":
        w = QLabel()
        w.setAlignment(Qt.AlignCenter)
        w.setMinimumSize(200, 120)
    elif kind == "hotkey":
        w = HotkeyButton(key, post)
    elif kind in ("hint", "plain"):
        w = _label(cls="dim", wrap=True)
    elif kind == "big":
        w = _label(cls="big", wrap=True)
    elif kind == "value":
        w = _label()
        w.setStyleSheet("font-weight: 600;")
    else:                                                     # label, entry (shown, not edited)
        w = _label(wrap=True)
    return w, extra


def show_control(kind, w, extra, st):
    """Put a model widget's state (app_qt.ui_state) into its Qt control – never sends anything back."""
    if kind not in ("title",):
        shown = bool(st.get("visible", True))
        if kind in ("hint", "plain", "big", "label"):
            shown = shown and bool(st.get("text"))            # empty lines take no room
        w.setVisible(shown)
    if "enabled" in st:
        w.setEnabled(st["enabled"])
    if st.get("tip") is not None and w.toolTip() != st["tip"]:
        w.setToolTip(st["tip"])
    if kind in ("check", "radio"):
        _set(w, st.get("text", ""))
        if w.isChecked() != bool(st.get("value")):
            w.setChecked(bool(st.get("value")))                 # setChecked does not emit clicked
    elif kind == "entry":
        if not w.hasFocus() and w.text() != st.get("value", ""):     # never overwrite while typing
            w.setText(st.get("value", ""))
    elif kind == "image":
        pil = st.get("pil")
        if pil is not getattr(w, "_pil", None):
            w._pil = pil
            if pil is None:
                w.setText(st.get("text", ""))
            else:
                w.setPixmap(pixmap_from_pil(pil, pil.height, w.devicePixelRatioF()))
    elif kind == "combo":
        if w.isEditable() != bool(st.get("editable")):
            w.setEditable(bool(st.get("editable")))
        values = st.get("values", [])
        if [w.itemText(i) for i in range(w.count())] != values:
            w.blockSignals(True)
            w.clear()
            w.addItems(values)
            w.blockSignals(False)
        if w.currentText() != st.get("value") and not (w.isEditable() and w.hasFocus()):
            w.blockSignals(True)
            i = w.findText(st.get("value", ""))
            if i >= 0:
                w.setCurrentIndex(i)
            elif w.isEditable():
                w.setEditText(st.get("value", ""))
            else:
                w.setCurrentIndex(-1)
            w.blockSignals(False)
    elif kind == "slider":
        name, s, value = extra
        _set(name, st.get("label", ""))
        _set(value, st.get("text", ""))
        if not s.isSliderDown():                                  # the user is dragging: no pull back
            s.blockSignals(True)
            s.setRange(round(st.get("lo", 0)), round(st.get("hi", 100)))
            s.setValue(round(st.get("value", 0)))
            s.blockSignals(False)
    elif kind in ("table", "chart", "log", "dashboard"):
        w.show_state(st)
    elif kind == "hotkey":
        w.show_text(st.get("text", ""))
        w.show_recording(bool(st.get("recording")))
    elif kind in ("box", "card"):
        pass
    else:                                                         # button, label, hint, value, title, big
        text = st.get("text", "")
        _set(w, text.upper() if kind == "title" else text)


class FormPage(QWidget):
    """A hand-made page (SPECS): one control per widget of the UI model, which does the work."""

    def __init__(self, post, title, spec):
        super().__init__()
        self._post = post
        self.controls = {}                 # key -> (kind, widget, extra)
        page, lay = _scroll_page(title)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        for item in spec:
            kind = item[0]
            if kind == "card":
                card = _card()
                cl = QVBoxLayout(card)
                cl.setContentsMargins(14, 12, 14, 12)
                cl.setSpacing(6)
                head = _label(cls="h2")
                cl.addWidget(head)
                self.controls[item[1]] = ("title", head, None)
                for row in item[2]:
                    self._add(row, cl)
                lay.addWidget(card)
            elif kind == "links":
                row = QHBoxLayout()
                for c in item[1]:
                    self._add(c, row)
                row.addStretch()
                lay.addLayout(row)
            else:
                self._add(item, lay)
        lay.addStretch()

    def _add(self, item, lay):
        kind = item[0]
        if kind == "row":
            row = QHBoxLayout()
            row.setSpacing(8)
            for c in item[1]:
                self._add(c, row)
            lay.addLayout(row)
            return
        if kind == "grid":                          # ("grid", columns, rows): the rows side by side (hotkeys)
            g = QGridLayout()
            g.setHorizontalSpacing(28)
            g.setVerticalSpacing(6)
            cols = item[1]
            per = -(-len(item[2]) // cols)            # down the first column, then the next
            for i, c in enumerate(item[2]):
                cell = QVBoxLayout()
                self._add(c, cell)
                g.addLayout(cell, i % per, i // per)
            for c in range(cols):
                g.setColumnStretch(c, 1)
            lay.addLayout(g)
            return
        if kind == "stretch":
            lay.addStretch()
            return
        w, extra = make_control(kind, item[1], self._post)
        lay.addWidget(w, 1 if kind == "hint" and isinstance(lay, QHBoxLayout) else 0)   # text beside: takes the room
        self.controls[item[1]] = (kind, w, extra)

    def show_states(self, states):
        for key, (kind, w, extra) in self.controls.items():
            st = states.get(key)
            if st is not None:
                show_control(kind, w, extra, st)


CHECKS = {"check:on": Qt.Checked, "check:off": Qt.Unchecked, "check:part": Qt.PartiallyChecked}   # uimodel.CHECK_*


def _check(item, tags):
    """A row tagged uimodel.CHECK_*: a tick box in the first column. Not user-checkable – the click goes to the
    model like any click on the row, the model toggles and sends the new tag."""
    state = next((CHECKS[t] for t in tags if t in CHECKS), None)
    if state is not None and item.data(0, Qt.CheckStateRole) != state:
        item.setCheckState(0, state)


class Table(QTreeWidget):
    """A table of the UI model (uimodel.Treeview): columns, rows (with groups), colours by tag, selection. A click
    on a row or a heading goes to the model (sorting, selecting, the server tab's tick boxes)."""

    def __init__(self, key, post):
        super().__init__()
        self._key, self._post = key, post
        self._shape = None
        self._fit = False
        self.setMinimumHeight(200)
        self.header().setStretchLastSection(False)
        self.header().setMinimumSectionSize(48)
        self.setAlternatingRowColors(False)
        self.setUniformRowHeights(True)
        self.header().setSectionsClickable(True)
        self.header().sectionClicked.connect(self._sort)
        self.itemClicked.connect(lambda item, _c: self._post("act", (self._key, ("click", item.data(0, Qt.UserRole)))))
        self._cols = []

    def _sort(self, index):
        if 0 <= index < len(self._cols):
            self._post("act", (self._key, ("sort", self._cols[index])))

    def show_state(self, st):
        cols = st.get("columns", [])
        rows = st.get("rows", [])
        shape = (tuple(tuple(c) for c in cols), tuple((r[0], r[1], r[2], tuple(r[3]), tuple(r[4])) for r in rows),
                 tuple(sorted(st.get("colours", {}).items())))
        if shape != self._shape and self._shape is not None and shape[0] == self._shape[0] and shape[2] == \
                self._shape[2] and [r[:2] for r in shape[1]] == [r[:2] for r in self._shape[1]]:
            self._shape = shape                       # same rows, other values (pings, counts): update in place
            self._update_cells(cols, rows, st.get("colours", {}))
        elif shape != self._shape:
            self._shape = shape
            self._cols = [c[0] for c in cols]
            tree = bool(cols) and cols[0][0] == "#0"
            self.setRootIsDecorated(tree and any(r[1] > 0 for r in rows))
            self.setHeaderLabels([c[1] for c in cols])
            for i, c in enumerate(cols):                  # numbers right-aligned: their heading too
                self.headerItem().setTextAlignment(i, (Qt.AlignRight if c[2] == "e" else Qt.AlignLeft) | Qt.AlignVCenter)
            self.clear()
            parents = {}
            colours = st.get("colours", {})
            for iid, depth, text, values, tags, opened in rows:
                cells = ([text] if tree else []) + list(values)
                item = QTreeWidgetItem(cells[:len(cols)] + [""] * max(0, len(cols) - len(cells)))
                item.setData(0, Qt.UserRole, iid)
                for i, (_cid, _t, anchor) in enumerate(cols):
                    if anchor == "e":
                        item.setTextAlignment(i, Qt.AlignRight | Qt.AlignVCenter)
                fg = next((colours[t] for t in tags if t in colours), None)
                if fg:
                    for i in range(len(cols)):
                        item.setForeground(i, QColor(fg))
                _check(item, tags)
                parent = parents.get(depth - 1)
                if parent is not None:
                    parent.addChild(item)
                else:
                    self.addTopLevelItem(item)
                parents[depth] = item
                item.setExpanded(True)
            fm = self.header().fontMetrics()
            widths = st.get("widths") or []
            stretch = st.get("stretch", 0) if 0 <= st.get("stretch", 0) < len(cols) else 0
            for i, c in enumerate(cols):
                self.header().setSectionResizeMode(i, self.header().ResizeMode.Interactive)
                self.resizeColumnToContents(i)
                least = widths[i] if i < len(widths) and i != stretch else 0    # the model's width: room for "…"
                self.setColumnWidth(i, max(self.columnWidth(i), fm.horizontalAdvance(c[1]) + 24, least))
            if cols:                  # the name column takes the rest (not always the first: "Wann" stays readable)
                self.header().setSectionResizeMode(stretch, self.header().ResizeMode.Stretch)
            self._fit_height()
        self._select(st)

    def fit_rows(self):
        """As tall as its rows (a table packed without expand – the server regions): no empty box below the last
        row, the page scrolls instead."""
        self._fit = True
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _fit_height(self):
        if not self._fit:
            return
        n = sum(1 for _i in self._items())
        row = self.sizeHintForRow(0) if n else 0
        self.setFixedHeight(self.header().sizeHint().height() + n * max(row, 1) + 2 * self.frameWidth() + 10)

    def _items(self):
        it = self.invisibleRootItem()
        stack = [it.child(i) for i in range(it.childCount() - 1, -1, -1)]
        while stack:
            item = stack.pop()
            yield item
            stack += [item.child(i) for i in range(item.childCount() - 1, -1, -1)]

    def _update_cells(self, cols, rows, colours):
        """Texts and colours of the rows already there (same rows in the same order) – no rebuild, no resizing,
        the scroll position stays."""
        tree = bool(cols) and cols[0][0] == "#0"
        for item, (_iid, _depth, text, values, tags, _o) in zip(self._items(), rows):
            cells = ([text] if tree else []) + list(values)
            fg = next((colours[t] for t in tags if t in colours), None)
            for i in range(len(cols)):
                value = cells[i] if i < len(cells) else ""
                if item.text(i) != value:
                    item.setText(i, value)
                item.setData(i, Qt.ForegroundRole, QColor(fg) if fg else None)
            _check(item, tags)

    def _select(self, st):
        sel = set(st.get("selection", []))
        mode = QTreeWidget.SingleSelection if st.get("selectable") else QTreeWidget.NoSelection
        if self.selectionMode() != mode:
            self.setSelectionMode(mode)
        if sel == getattr(self, "_sel", None) and sel == {i.data(0, Qt.UserRole) for i in self.selectedItems()}:
            return                                # nothing changed: no walk over all rows 4×/s
        self._sel = sel
        it = self.invisibleRootItem()
        stack = [it.child(i) for i in range(it.childCount())]
        self.blockSignals(True)
        while stack:
            item = stack.pop()
            on = item.data(0, Qt.UserRole) in sel
            if item.isSelected() != on:
                item.setSelected(on)
            stack += [item.child(i) for i in range(item.childCount())]
        self.blockSignals(False)


class LogView(QPlainTextEdit):
    """The log (App._log_entries, filtered by the categories ticked) – coloured by category, follows new lines.
    New entries are appended (the entries are the App's own tuples, so the last one shown is found by identity);
    only another colour scheme or ``rev`` (filter changed, log cleared) rebuilds the whole text."""

    MAX_LINES = 400

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setMinimumHeight(360)
        self.setMaximumBlockCount(self.MAX_LINES)        # old lines drop off by themselves
        self._last = None                                # last entry shown
        self._look = None

    def _row(self, entry, col):
        ts, cat, text = entry
        msg = col["Fehler"] if cat == "Fehler" else col["text"]
        return (f'<span style="color:{col["ts"]}">{html.escape(ts)}</span>&nbsp;&nbsp;'
                f'<span style="color:{col.get(cat, col["text"])}">{html.escape(_(cat))}</span>&nbsp;&nbsp;'
                f'<span style="color:{msg}">{html.escape(text)}</span>')

    def show_state(self, st):
        from .theme import LOG_COLORS
        lines = list(st.get("lines", ()))
        look = (st.get("dark"), st.get("rev"))           # colours / filter or cleared log
        last = lines[-1] if lines else None
        if last is self._last and look == self._look:
            return
        col = LOG_COLORS[bool(look[0])]
        bar = self.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 4
        start = None
        if look == self._look and self._last is not None:
            start = next((i + 1 for i in range(len(lines) - 1, -1, -1) if lines[i] is self._last), None)
        if start is None:                                # filter/colours changed, log cleared: everything again
            # one paragraph (block) per line, like appendHtml: the block limit then drops single old lines
            self.document().setHtml("".join(f'<p style="margin:0">{self._row(e, col)}</p>'
                                            for e in lines[-self.MAX_LINES:]))
        else:
            for e in lines[start:]:
                self.appendHtml(self._row(e, col))
        self._last, self._look = last, look
        if at_end:
            bar.setValue(bar.maximum())


class HotkeyButton(QPushButton):
    """A hotkey in the settings: click, then press the new combination (Esc cancels, Del switches it off).
    The key presses go to the App, which checks them (hotkeys.combo_from_keys)."""

    def __init__(self, key, post):
        super().__init__()
        self._key, self._post = key, post
        self._recording = False
        self.setMinimumWidth(170)
        self.clicked.connect(self._start)

    def _start(self):
        self._recording = True
        self.setFocus()
        self._post("hk_record", self._key)

    def show_text(self, text):
        _set(self, text)

    def keyPressEvent(self, e):
        if not self._recording:
            return super().keyPressEvent(e)
        k = e.key()
        if k in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta, Qt.Key_AltGr):
            return                                            # still holding modifiers
        mods = [name for name, flag in (("ctrl", Qt.ControlModifier), ("alt", Qt.AltModifier),
                                        ("shift", Qt.ShiftModifier)) if e.modifiers() & flag]
        if Qt.Key_A <= k <= Qt.Key_Z:
            sym = chr(k).lower()
        elif Qt.Key_0 <= k <= Qt.Key_9 and not (e.modifiers() & Qt.KeypadModifier):
            sym = chr(k)
        elif Qt.Key_F1 <= k <= Qt.Key_F24:
            sym = f"F{k - Qt.Key_F1 + 1}"
        else:
            sym = {Qt.Key_Escape: "Escape", Qt.Key_Delete: "Delete", Qt.Key_Backspace: "BackSpace"}.get(k, "")
        vk = (e.nativeVirtualKey() or None) if sys.platform == "win32" else None
        self._post("hk_key", (self._key, mods, sym, vk))

    def focusOutEvent(self, e):
        if self._recording:
            self._recording = False
            self._post("hk_cancel", self._key)
        super().focusOutEvent(e)

    def show_recording(self, on: bool):
        """The App's view: once it has recorded (or cancelled), stop sending keys."""
        if on:
            self._seen = True
        elif getattr(self, "_seen", False):
            self._seen = self._recording = False


class Chart(QWidget):
    """The statistics charts (trendchart.TrendChart's data) drawn with Qt: columns, or a line for temperatures;
    hovering a column/point shows its tooltip text."""

    PANEL_H = 180

    def __init__(self):
        super().__init__()
        self._st = None
        self._hits = []
        self.setMouseTracking(True)
        self.setMinimumHeight(self.PANEL_H)

    def show_state(self, st):
        key = (id(st.get("data")), st.get("dark"), tuple(st.get("panels", ())))
        if self._st is None or key != self._key:
            self._key = key
            self._st = st
            self.setMinimumHeight(len(st.get("panels", ())) * (self.PANEL_H + 10))
            self.update()

    def paintEvent(self, _e):
        from PySide6.QtGui import QPainter, QPen
        from .trendchart import BOTTOM, COLORS, LEFT, RIGHT, TOP, columns, segments
        st = self._st
        self._hits = []
        if not st or not st.get("data"):
            return
        col = COLORS[bool(st.get("dark", True))]
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        width = max(200, self.width())
        for n, role in enumerate(st.get("panels", ())):
            d = st["data"].get(role)
            if not d:
                continue
            top = n * (self.PANEL_H + 10)
            p.setPen(QColor(col["text"]))
            f = p.font()
            f.setBold(True)
            p.setFont(f)
            p.drawText(8, top + 14, d["title"])
            f.setBold(False)
            p.setFont(f)
            y0, y1 = top + TOP, top + self.PANEL_H - BOTTOM
            bars = d["bars"]
            if not any(v is not None for v, _l, _t in bars):
                p.setPen(QColor(col["dim"]))
                p.drawText(LEFT, round((y0 + y1) / 2), d["empty"])
                continue
            lo = d.get("min", 0)
            scale = (y1 - y0) / max(1e-9, d["max"] - lo)
            for value, label in d["ticks"]:
                y = y1 - (value - lo) * scale
                p.setPen(QPen(QColor(col["grid"]), 1))
                p.drawLine(LEFT, round(y), width - RIGHT, round(y))
                p.setPen(QColor(col["dim"]))
                p.drawText(0, round(y) - 8, LEFT - 6, 16, Qt.AlignRight | Qt.AlignVCenter, label)
            xs = columns(len(bars), width)
            every = max(1, -(-len(xs) * 46 // max(1, width - LEFT - RIGHT)))
            newest = max((i for i, (v, _l, _t) in enumerate(bars) if v is not None), default=None)
            slot = (xs[1][0] - xs[0][0]) if len(xs) > 1 else 40
            line = []
            for i, ((value, label, tip), (x0, x1)) in enumerate(zip(bars, xs)):
                mid = (x0 + x1) / 2
                if (len(xs) - 1 - i) % every == 0:
                    p.setPen(QColor(col["dim"]))
                    p.drawText(round(mid) - 30, round(y1) + 4, 60, 16, Qt.AlignHCenter | Qt.AlignTop, label)
                if value is None:
                    line.append(None)
                    continue
                if d.get("kind") == "line":
                    y = y1 - (value - lo) * scale
                    line.append((mid, y))
                else:
                    y = y1 - max(2.0, value * scale)
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(col[role]))
                    p.drawRoundedRect(round(x0), round(y), round(x1 - x0), round(y1 - y) + 4, 4, 4)
                    p.fillRect(round(x0), round(y1) - 2, round(x1 - x0), 2, QColor(col[role]))
                if i == newest:
                    p.setPen(QColor(col["text"]))
                    ly = (y1 - (value - lo) * scale) - 6
                    p.drawText(round(mid) - 40, round(ly) - 16, 80, 16, Qt.AlignHCenter | Qt.AlignBottom, d["last"])
                self._hits.append((mid - slot / 2, y0 - 10, mid + slot / 2, y1, tip))
            if d.get("kind") == "line":
                p.setPen(QPen(QColor(col[role]), 2))
                for a, b in segments(line):
                    p.drawLine(round(a[0]), round(a[1]), round(b[0]), round(b[1]))
                p.setBrush(QColor(col[role]))
                for pt in line:
                    if pt is not None:
                        p.drawEllipse(round(pt[0]) - 4, round(pt[1]) - 4, 8, 8)
        p.end()

    def mouseMoveEvent(self, e):
        from PySide6.QtWidgets import QToolTip
        x, y = e.position().x(), e.position().y()
        hit = next((h for h in self._hits if h[0] <= x <= h[2] and h[1] <= y <= h[3]), None)
        if hit:
            QToolTip.showText(e.globalPosition().toPoint(), hit[4], self)
        else:
            QToolTip.hideText()


# Heatmap (average kills 0–4): the sequential blue ramp of the dataviz palette (validated, same blue as "Killer" in
# the trend chart). Light surface: more = darker; dark surface: more = lighter (near zero recedes to the surface).
HEAT_RAMP = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281")
BAR_NEUTRAL = {True: "#6b7079", False: "#a3a8b0"}     # map bars: a plain count, no identity – neutral grey


def heat_colour(value: float, dark: bool, top: float = 4.0) -> QColor:
    """Colour of a heatmap cell: ``value`` 0..top along the ramp."""
    ramp = HEAT_RAMP[::-1] if dark else HEAT_RAMP
    f = min(1.0, max(0.0, value / top)) * (len(ramp) - 1)
    i = min(len(ramp) - 2, int(f))
    a, b, t = QColor(ramp[i]), QColor(ramp[i + 1]), f - i
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


def ink_on(colour: QColor) -> QColor:
    """Text colour on a filled cell: dark ink on light cells, light ink on dark ones."""
    lum = 0.2126 * colour.redF() + 0.7152 * colour.greenF() + 0.0722 * colour.blueF()
    return QColor("#111214") if lum > 0.45 else QColor("#f0efec")


class MapBars(QWidget):
    """Most played maps: one row each – name, a bar for the rounds, the count and the results (stats page)."""
    ROW = 26

    def __init__(self):
        super().__init__()
        self._rows, self._max, self._dark = [], 1, True
        self.setMinimumHeight(self.ROW)

    def set_rows(self, rows, top, dark):
        self._rows, self._max, self._dark = list(rows), max(1, top), dark
        self.setMinimumHeight(max(self.ROW, len(self._rows) * self.ROW))
        self.update()

    def paintEvent(self, _e):
        from PySide6.QtGui import QPainter
        c = qt_theme.PALETTE[self._dark]
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        name_w = min(190, max(110, w // 4))
        info_w = min(230, max(120, w // 3))
        bar_x, bar_w = name_w + 8, max(40, w - name_w - info_w - 60)
        fm = p.fontMetrics()
        for i, (name, n, info) in enumerate(self._rows):
            y = i * self.ROW
            mid = y + self.ROW / 2
            p.setPen(QColor(c["fg"]))
            p.drawText(0, y, name_w, self.ROW, Qt.AlignLeft | Qt.AlignVCenter, fm.elidedText(name, Qt.ElideRight, name_w))
            length = max(3.0, bar_w * n / self._max)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(BAR_NEUTRAL[self._dark]))
            p.drawRoundedRect(bar_x, round(mid - 5), round(length), 10, 4, 4)
            p.setPen(QColor(c["fg"]))
            p.drawText(round(bar_x + length + 6), y, 40, self.ROW, Qt.AlignLeft | Qt.AlignVCenter, str(n))
            p.setPen(QColor(c["dim"]))
            p.drawText(w - info_w, y, info_w, self.ROW, Qt.AlignRight | Qt.AlignVCenter,
                       fm.elidedText(info, Qt.ElideRight, info_w))
        p.end()


class Heatmap(QWidget):
    """Map × killer, average kills: rows = maps, columns = killers, cell colour = Ø kills (0–4) with the value
    written in it; empty cells = too few rounds. Hover: the cell's text with its number of rounds."""
    HEAD, ROW, LEGEND = 28, 26, 30

    def __init__(self):
        super().__init__()
        self._d, self._dark, self._hits = None, True, []
        self.setMouseTracking(True)

    def set_data(self, d, dark):
        self._d, self._dark = d, dark
        rows = len(d.rows) if d else 0
        self.setMinimumHeight(self.HEAD + rows * self.ROW + self.LEGEND if rows else 0)
        self.update()

    def paintEvent(self, _e):
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QLinearGradient, QPainter
        d = self._d
        self._hits = []
        if not d or not d.rows:
            return
        c = qt_theme.PALETTE[self._dark]
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        fm = p.fontMetrics()
        name_w = min(190, max(110, self.width() // 4))
        cols = max(1, len(d.columns))
        cell_w = max(36, min(96, (self.width() - name_w) / cols))
        from .dashboard import MATRIX_MIN, short_killer
        p.setPen(QColor(c["dim"]))
        for j, k in enumerate(d.columns):
            x = name_w + j * cell_w
            p.drawText(QRectF(x, 0, cell_w, self.HEAD), Qt.AlignHCenter | Qt.AlignVCenter,
                       fm.elidedText(short_killer(k), Qt.ElideRight, round(cell_w) - 4))
        for i, m in enumerate(d.rows):
            y = self.HEAD + i * self.ROW
            p.setPen(QColor(c["fg"]))
            p.drawText(QRectF(0, y, name_w - 8, self.ROW), Qt.AlignLeft | Qt.AlignVCenter,
                       fm.elidedText(m, Qt.ElideRight, name_w - 8))
            for j, k in enumerate(d.columns):
                rect = QRectF(name_w + j * cell_w + 1, y + 1, cell_w - 2, self.ROW - 2)     # 2 px surface gap
                cell = d.cells.get((m, k))
                if cell is None:
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(c["hover"]))
                    p.drawRoundedRect(rect.adjusted(cell_w / 2 - 2, self.ROW / 2 - 3, -(cell_w / 2 - 2),
                                                    -(self.ROW / 2 - 3)), 2, 2)
                    continue
                avg, n = cell
                fill = heat_colour(avg, self._dark)
                p.setPen(Qt.NoPen)
                p.setBrush(fill)
                p.drawRoundedRect(rect, 4, 4)
                p.setPen(ink_on(fill))
                p.drawText(rect, Qt.AlignCenter, f"{avg:.1f}")
                self._hits.append((rect, _("{map} · {killer}: Ø {kills} Kills ({n} Runden)", map=m, killer=k,
                                           kills=f"{avg:.1f}", n=n)))
        # legend: the ramp from 0 to 4 kills
        ly = self.HEAD + len(d.rows) * self.ROW + 10
        grad = QLinearGradient(name_w, 0, name_w + 160, 0)
        for t in range(5):
            grad.setColorAt(t / 4, heat_colour(t, self._dark))
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(name_w, ly, 160, 8), 4, 4)
        p.setPen(QColor(c["dim"]))
        p.drawText(QRectF(name_w - 30, ly - 5, 24, 18), Qt.AlignRight | Qt.AlignVCenter, "0")
        p.drawText(QRectF(name_w + 166, ly - 5, 260, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   _("4 Kills · leer = weniger als {n} Runden", n=MATRIX_MIN))
        p.end()

    def mouseMoveEvent(self, e):
        from PySide6.QtWidgets import QToolTip
        pos = e.position()
        hit = next((t for r, t in self._hits if r.contains(pos)), None)
        if hit:
            QToolTip.showText(e.globalPosition().toPoint(), hit, self)
        else:
            QToolTip.hideText()


class DashboardView(QWidget):
    """The statistics dashboard (dashboard.Dashboard): key figure tiles, the most played maps, killer × map."""

    def __init__(self):
        super().__init__()
        self._shown = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.empty = _label(cls="dim")
        lay.addWidget(self.empty)
        self.tiles_box = QWidget()
        self.grid = QGridLayout(self.tiles_box)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(12)
        self.tiles = []
        for i in range(6):
            card = _card()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            box = FactBox(bar=True)
            box.sub.setWordWrap(True)                 # "no killer rounds with stats data": wraps in a narrow window
            cl.addWidget(box)
            self.grid.addWidget(card, 0, i)
            self.tiles.append((card, box))
        lay.addWidget(self.tiles_box)
        self.maps_card, self.maps = self._chart_card(lay, _("Maps – am häufigsten gespielt"), MapBars())
        self.heat_card, self.heat = self._chart_card(lay, _("Killer × Map – Ø Kills laut Stats-Seite"), Heatmap())
        self.heat_note = _label(cls="dim", wrap=True)
        self.heat_card.layout().addWidget(self.heat_note)

    @staticmethod
    def _chart_card(lay, title, widget):
        card = _card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 12, 14, 12)
        cl.setSpacing(8)
        cl.addWidget(_label(title.upper(), "h2"))
        cl.addWidget(widget)
        lay.addWidget(card)
        return card, widget

    def show_state(self, st):
        d, dark = st.get("data"), bool(st.get("dark", True))
        key = (id(d), dark)
        if key == self._shown:
            return
        self._shown = key
        has = d is not None and not d.empty
        self.empty.setVisible(d is not None and bool(d.empty))
        _set(self.empty, d.empty if d is not None else "")
        for w in (self.tiles_box, self.maps_card, self.heat_card):
            w.setVisible(has)
        if not has:
            return
        for i, (card, box) in enumerate(self.tiles):
            card.setVisible(i < len(d.tiles))
            if i < len(d.tiles):
                box.show_fact(d.tiles[i])
        self.maps.set_rows(d.maps, d.maps_max, dark)
        self.heat.set_data(d, dark)
        self.heat.setVisible(bool(d.rows))
        _set(self.heat_note, "" if d.rows else _("Noch keine Killer-Runden mit Ergebnis von der Stats-Seite "
                                                 "(Einstellungen → Mehr → Offizielle Match-Daten)."))
        self.heat_note.setVisible(not d.rows)


def _grows(node) -> bool:
    """A table, chart or the log below this node: it may take the free height of the page."""
    return (node.get("kind") in ("table", "chart", "log") and not node.get("fit")) or \
        any(_grows(c) for c in node.get("children", ()))


def _fills(node) -> bool:
    """A notebook below this node fills the page (packed with expand): the page does not scroll as a whole."""
    return (node.get("kind") == "tabs" and bool(node.get("fill"))) or any(_fills(c) for c in node.get("children", ()))


class AutoPage(QWidget):
    """A page built from the structure of a tab of the UI model (app_qt.ui_layout): frames → cards/rows,
    notebooks → tabs, tables, charts and controls like FormPage (Statistik, Server, Erkennung, Log, dialogs)."""

    def __init__(self, post, title, node):
        super().__init__()
        self._post = post
        self.controls = {}                 # key -> (kind, widget, extra)
        self._tabs = []                    # (QTabWidget, [keys of each page])
        self._all = []
        fill = _fills(node) if node else False
        page, lay = _scroll_page(title, scroll=not fill)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        if node:
            self._build(node, lay, self._all, top=True)
        if not fill:
            lay.addStretch()

    def _build(self, n, lay, keys, top=False):
        kind, key = n["kind"], n["key"]
        keys.append(key)
        if kind in ("box", "card"):
            holder = _card() if kind == "card" else QWidget()
            v = QVBoxLayout(holder)
            v.setContentsMargins(*((14, 12, 14, 12) if kind == "card" else (0, 0, 0, 0)))
            v.setSpacing(6)
            if kind == "card":
                head = _label(cls="h2")
                v.addWidget(head)
                self.controls[key + "#title"] = ("title", head, None)
            kids = n.get("children", [])
            if n.get("grid"):                         # e.g. the game languages
                g = QGridLayout()
                g.setHorizontalSpacing(14)
                for c in kids:
                    cell = QVBoxLayout()
                    self._build(c, cell, keys)
                    g.addLayout(cell, *c.get("cell", (0, 0)))
                g.setColumnStretch(g.columnCount(), 1)
                v.addLayout(g)
                lay.addWidget(holder, 1 if top and _grows(n) else 0)
                self.controls[key] = (kind, holder, None)
                return
            inner = QHBoxLayout() if n.get("row") else v
            if inner is not v:
                inner.setSpacing(8)
                v.addLayout(inner)
            first = [c for c in kids if c.get("side") != "right"]
            last = list(reversed([c for c in kids if c.get("side") == "right"]))
            for c in first:
                self._build(c, inner, keys, top=top and inner is v)    # a table further down still gets the height
            if n.get("row"):
                inner.addStretch()
            for c in last:
                self._build(c, inner, keys, top=top and inner is v)
            lay.addWidget(holder, 1 if top and _grows(n) else 0)
            self.controls[key] = (kind, holder, None)
            return
        if kind == "tabs":
            tw = QTabWidget()
            fill = bool(n.get("fill"))
            pages = []
            for c in n.get("children", []):
                pw = QWidget()
                pl = QVBoxLayout(pw)
                pl.setContentsMargins(8, 8, 8, 8)
                ks = []
                self._build(c, pl, ks, top=fill)       # filling tabs: a table takes the height of its page
                pl.addStretch()
                if fill:                               # each page scrolls on its own, the filters stay on top
                    pw.setObjectName("page")
                    sa = QScrollArea()
                    sa.setWidgetResizable(True)
                    sa.setFrameShape(QFrame.NoFrame)
                    sa.setWidget(pw)
                    tw.addTab(sa, "")
                else:
                    tw.addTab(pw, "")
                pages.append(ks)
                keys.extend(ks)
            tw.currentChanged.connect(lambda i, k=key: self._post("act", (k, i)))
            lay.addWidget(tw, 1 if fill else 0)
            self._tabs.append((key, tw, pages))
            self.controls[key] = ("tabs", tw, None)
            return
        w, extra = make_control(kind, key, self._post)
        if kind == "table" and n.get("fit"):
            w.fit_rows()
        grow = kind in ("table", "chart", "log") or (kind == "hint" and isinstance(lay, QHBoxLayout))
        if kind in ("button", "combo") and not isinstance(lay, QHBoxLayout):
            lay.addWidget(w, 0, Qt.AlignLeft)             # a button on a line of its own keeps its size
        else:
            lay.addWidget(w, 1 if grow else 0)
        self.controls[key] = (kind, w, extra)

    def visible_keys(self) -> set:
        """Keys to read now: everything except the pages of tabs that are not on display."""
        hidden = set()
        for _key, tw, pages in self._tabs:
            for i, ks in enumerate(pages):
                if i != tw.currentIndex():
                    hidden.update(ks)
        return set(self._all) - hidden

    def show_states(self, states):
        for key, (kind, w, extra) in self.controls.items():
            if kind == "tabs":
                st = states.get(key)
                if st:
                    tw = w
                    for i, text in enumerate(st.get("tabs", [])[:tw.count()]):
                        if tw.tabText(i) != text:
                            tw.setTabText(i, text)
                    if tw.currentIndex() != st.get("index", 0):
                        tw.blockSignals(True)
                        tw.setCurrentIndex(st.get("index", 0))
                        tw.blockSignals(False)
                continue
            if key.endswith("#title"):
                st = states.get(key[:-6])
                if st is not None:
                    show_control("title", w, extra, st)
                continue
            st = states.get(key)
            if st is not None:
                show_control(kind, w, extra, st)


class MapsPage(QWidget):
    """Search + list of maps (grouped by realm) and a preview of the selected one (1.58.1); double click / Enter /
    "Anzeigen" shows a map."""

    def __init__(self, post):
        super().__init__()
        self._post = post
        self._preview_key = None
        self._preview_src = None
        self._shown_current = None
        page, lay = _scroll_page("Maps", scroll=False)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        row = QHBoxLayout()
        row.addWidget(_label(_("Suche")))
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda t: self._post("search", t))
        self.search.returnPressed.connect(self._pick_first)
        row.addWidget(self.search, 1)
        lay.addLayout(row)
        body = QHBoxLayout()
        body.setSpacing(12)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(220)
        self.tree.itemActivated.connect(self._picked)
        self.tree.currentItemChanged.connect(self._selected)
        body.addWidget(self.tree, 2)
        card = _card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 12, 14, 12)
        cl.setSpacing(6)
        self.p_name = _label(cls="map", wrap=True)
        self.p_realm = _label(cls="dim", wrap=True)
        self.p_pic = QLabel()
        self.p_pic.setObjectName("thumb")
        self.p_pic.setAlignment(Qt.AlignCenter)
        self.p_pic.setMinimumSize(160, 160)
        self.p_pic.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)   # scales with the card, not the image
        self.p_show = QPushButton(_("Anzeigen"))
        self.p_show.setObjectName("primary")
        self.p_show.setToolTip(_tip("Anzeigen"))
        self.p_show.clicked.connect(self._show_selected)
        cl.addWidget(self.p_name)
        cl.addWidget(self.p_realm)
        cl.addWidget(self.p_pic, 1)
        cl.addWidget(self.p_show, 0, Qt.AlignLeft)
        body.addWidget(card, 3)
        lay.addLayout(body, 1)
        lay.addWidget(_label(_("Doppelklick oder „Anzeigen“ zeigt die Map. Die Erkennung übernimmt beim nächsten "
                               "Match wieder."), "dim", wrap=True))
        prow = QHBoxLayout()
        b = QPushButton(_("Kartenbild hinzufügen …"))
        b.setToolTip(_tip("Kartenbild hinzufügen …"))
        b.clicked.connect(lambda: self._post("add_picture"))
        prow.addWidget(b)
        prow.addWidget(_label(_("eigenes Bild für eine Map (Hintergrund wird entfernt)"), "dim"))
        prow.addStretch()
        lay.addLayout(prow)
        self._items = None
        self.show_preview(None)

    def _selected(self, item, _prev=None):
        data = item.data(0, Qt.UserRole) if item is not None else None
        if data:
            self._post("map_preview", tuple(data))

    def _show_selected(self):
        if self._preview_key:
            self._post("show_map", tuple(self._preview_key))

    def show_preview(self, p):
        """p = (map_id, variant, name, realm, PIL picture or None) or None (nothing selected)."""
        key = tuple(p[:2]) if p else None
        if p is not None and key == self._preview_key and p[4] is self._preview_src:
            return
        self._preview_key, self._preview_src = key, (p[4] if p else None)
        _set(self.p_name, p[2] if p else _("Keine Map gewählt"))
        _set(self.p_realm, p[3] if p else _("Links eine Map wählen – hier erscheint ihre Karte."))
        self.p_show.setEnabled(p is not None)
        self._scale_preview()

    def _scale_preview(self):
        src = self._preview_src
        if src is None:
            self.p_pic.clear()
            return
        w, h = max(1, self.p_pic.width() - 12), max(1, self.p_pic.height() - 12)
        fit_h = max(1, min(h, round(w * src.height / src.width)))
        self.p_pic.setPixmap(pixmap_from_pil(src, fit_h, self.devicePixelRatioF()))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._scale_preview()

    def _picked(self, item, _col=0):
        data = item.data(0, Qt.UserRole)
        if data:
            self._post("show_map", tuple(data))

    def _pick_first(self):
        if self._items:
            self._post("show_map", (self._items[0][2], self._items[0][3]))

    def show_maps(self, items, current):
        if items != self._items:
            self._items = list(items)
            self.tree.blockSignals(True)
            self.tree.clear()
            self.tree.blockSignals(False)
            groups = {}
            for realm, label, mid, v in items:
                if realm not in groups:
                    groups[realm] = QTreeWidgetItem([realm])
                    self.tree.addTopLevelItem(groups[realm])
                child = QTreeWidgetItem([label])
                child.setData(0, Qt.UserRole, [mid, v])
                groups[realm].addChild(child)
            if self.search.text():
                self.tree.expandAll()
        for i in range(self.tree.topLevelItemCount()):
            g = self.tree.topLevelItem(i)
            for j in range(g.childCount()):
                c = g.child(j)
                on = current is not None and list(current) == c.data(0, Qt.UserRole)
                font = c.font(0)
                if font.bold() != on:
                    font.setBold(on)
                    c.setFont(0, font)
                if on and current != self._shown_current:     # a new map is shown: open its realm, mark it
                    g.setExpanded(True)
                    self.tree.blockSignals(True)
                    self.tree.setCurrentItem(c)
                    self.tree.blockSignals(False)
                    self.tree.scrollToItem(c)
        self._shown_current = current


class DialogWindow(QDialog):
    """A dialog of the UI model (Zuordnen, Kartenbild hinzufügen): built like AutoPage, not modal; closing it
    (X, Esc) destroys the model's dialog too."""

    def __init__(self, parent, post, key, title, node):
        super().__init__(parent)
        self._post, self._key = post, key
        self.closing_from_app = False
        self.setWindowTitle(title)
        self.setModal(False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.page = AutoPage(post, title, node)
        lay.addWidget(self.page)
        self.resize(640, 560)

    def done(self, r):                            # Esc / X: the model's dialog goes too
        if not self.closing_from_app:
            self._post("dlg_close", self._key)
        super().done(r)


def nav_icon(key: str, colour: str, ratio: float = 1.0, alert: bool = False) -> QPixmap:
    """One icon of the navigation, drawn as lines (not a font character: symbols from different fonts came out
    in different sizes and places). All in a NAV_ICON box, 1.6 px lines; ``alert`` = amber dot (log)."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QPainter, QPen
    size = NAV_ICON
    pm = QPixmap(round(size * ratio), round(size * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    col = QColor(colour)
    pen = QPen(col, 1.6)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    m, c = 2.5, size / 2                       # margin, centre
    full = QRectF(m, m, size - 2 * m, size - 2 * m)
    if key == "overview":                      # target: ring + dot
        p.drawEllipse(QPointF(c, c), 6.5, 6.5)
        p.setBrush(col)
        p.drawEllipse(QPointF(c, c), 2.4, 2.4)
    elif key == "maps":                        # four tiles
        g = (size - 2 * m - 2) / 2
        for x in (m, m + g + 2):
            for y in (m, m + g + 2):
                p.drawRoundedRect(QRectF(x, y, g, g), 1.5, 1.5)
    elif key == "overlay":                     # a screen with a picture in its left part
        p.drawRoundedRect(full, 2, 2)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(m + 2.5, m + 2.5, (size - 2 * m) * 0.4, size - 2 * m - 5), 1, 1)
    elif key == "stats":                       # three columns on a base line
        base = size - m
        for i, h in enumerate((5, 11, 8)):
            x = m + 1.5 + i * 4.6
            p.drawLine(QPointF(x, base - 1.5), QPointF(x, base - 1.5 - h))
        p.drawLine(QPointF(m, base), QPointF(size - m, base))
    elif key == "server":                      # globe
        p.drawEllipse(QPointF(c, c), 6.5, 6.5)
        p.drawEllipse(QPointF(c, c), 2.8, 6.5)
        p.drawLine(QPointF(c - 6.5, c), QPointF(c + 6.5, c))
    elif key == "settings":                    # gear: ring + eight teeth
        import math
        p.drawEllipse(QPointF(c, c), 4.6, 4.6)
        p.drawEllipse(QPointF(c, c), 1.7, 1.7)
        tooth = QPen(col, 2.6)
        tooth.setCapStyle(Qt.FlatCap)
        p.setPen(tooth)
        for i in range(8):
            a = i * math.pi / 4 + math.pi / 8
            p.drawLine(QPointF(c + 5.2 * math.cos(a), c + 5.2 * math.sin(a)),
                       QPointF(c + 7.4 * math.cos(a), c + 7.4 * math.sin(a)))
    elif key == "detect":                      # scan frame: four corners + a dot
        k = 4.0
        for (x, y, dx, dy) in ((m, m, 1, 1), (size - m, m, -1, 1), (m, size - m, 1, -1), (size - m, size - m, -1, -1)):
            p.drawLine(QPointF(x, y), QPointF(x + dx * k, y))
            p.drawLine(QPointF(x, y), QPointF(x, y + dy * k))
        p.setBrush(col)
        p.drawEllipse(QPointF(c, c), 2.2, 2.2)
    elif key == "log":                         # lines of text
        for i, w in enumerate((1.0, 0.75, 0.9)):
            y = m + 2 + i * 5
            p.drawLine(QPointF(m, y), QPointF(m + (size - 2 * m) * w, y))
    if alert:
        from .theme import DOT
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(DOT["warn"]))
        p.drawEllipse(QPointF(size - 3.5, size - 3.5), 3.5, 3.5)
    p.end()
    return pm


class MainWindow(QMainWindow):
    def __init__(self, post, icon_path: str | None = None, layouts: dict | None = None):
        super().__init__()
        self._post = post
        self.allow_close = False          # closing = quitting the program, through the App
        self.geometry_changed = False     # read and reset by the App (it saves the geometry, debounced)
        self.minimised = False
        self.setWindowTitle("DbD Map Scout")
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(190)
        self.stack = QStackedWidget()
        self.overview = OverviewPage(post)
        self.maps = MapsPage(post)
        self.forms = {key: FormPage(post, _(label), SPECS[key]) for key, label in PAGES if key in SPECS}
        for key, label in PAGES:
            if key in AUTO_PAGES and (layouts or {}).get(key):
                self.forms[key] = AutoPage(post, _(label), layouts[key])
        self.nav.setIconSize(QSize(NAV_ICON, NAV_ICON))
        for key, label in PAGES:
            item = QListWidgetItem(_(label))
            item.setData(Qt.UserRole, key)
            self.nav.addItem(item)
            page = {"overview": self.overview, "maps": self.maps}.get(key) or self.forms.get(key) or QWidget()
            self.stack.addWidget(page)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._page_changed)
        lay.addWidget(self.nav)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        # OK/Cancel or a note (App._ask/_inform) – a bar, not a modal dialog
        self.question = QFrame()
        self.question.setObjectName("question")
        ql = QHBoxLayout(self.question)
        ql.setContentsMargins(16, 10, 16, 10)
        self.question_text = _label(wrap=True)
        ql.addWidget(self.question_text, 1)
        self.question_ok = QPushButton(_("OK"))
        self.question_ok.setObjectName("primary")
        self.question_ok.clicked.connect(lambda: post("answer", True))
        self.question_cancel = QPushButton(_("Abbrechen"))
        self.question_cancel.clicked.connect(lambda: post("answer", False))
        ql.addWidget(self.question_ok, alignment=Qt.AlignVCenter)
        ql.addWidget(self.question_cancel, alignment=Qt.AlignVCenter)
        self.question.hide()
        self._question = None
        right.addWidget(self.question)
        right.addWidget(self.stack, 1)
        lay.addLayout(right, 1)
        self.setCentralWidget(central)
        self.resize(1100, 760)
        self.setMinimumSize(760, 520)
        self._log_alert = False
        self._dark = True
        self._nav_icons()
        self.dialogs = {}                 # dialog path (UI model) -> DialogWindow

    def _page_changed(self, row):
        self.stack.setCurrentIndex(row)
        self._post("page", PAGES[row][0])                          # the App fills it now

    def current_key(self) -> str:
        return PAGES[max(0, self.nav.currentRow())][0]

    def show_states(self, page, states):
        if page in self.forms:
            self.forms[page].show_states(states)

    def visible_keys(self, page) -> set:
        f = self.forms.get(page)
        return f.visible_keys() if isinstance(f, AutoPage) else set()

    def open_dialog(self, key, title, node):
        self.close_dialog(key)
        dlg = DialogWindow(self, self._post, key, title, node)
        dlg.setStyleSheet(self.styleSheet())
        self.dialogs[key] = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def close_dialog(self, key):
        dlg = self.dialogs.pop(key, None)
        if dlg is not None:
            dlg.closing_from_app = True
            dlg.close()

    def show_dialog_states(self, key, states):
        dlg = self.dialogs.get(key)
        if dlg is not None:
            dlg.page.show_states(states)

    def choose_file(self, mode, title, initial, pattern="JSON (*.json)"):
        """Non-modal file dialog (Qt's own, not the system one: no second message loop); the result goes out as
        post("file", path or None)."""
        from PySide6.QtWidgets import QFileDialog
        dlg = QFileDialog(self, title, initial, f"{pattern};;* (*.*)")
        dlg.setOption(QFileDialog.DontUseNativeDialog, True)
        dlg.setAcceptMode(QFileDialog.AcceptSave if mode == "save" else QFileDialog.AcceptOpen)
        dlg.setFileMode(QFileDialog.AnyFile if mode == "save" else QFileDialog.ExistingFile)
        if mode == "save":
            dlg.setDefaultSuffix("json")
        dlg.fileSelected.connect(lambda path: self._post("file", path))
        dlg.rejected.connect(lambda: self._post("file", None))
        dlg.open()
        self._file_dialog = dlg                       # keep it alive while it is open

    def show_question(self, q):
        """q = (title, text, ask) or None; ask False = only a note with OK."""
        if q == self._question:
            return
        self._question = q
        self.question.setVisible(q is not None)
        if q is not None:
            self.question_text.setText(f"<b>{html.escape(q[0])}</b><br>" + html.escape(q[1]).replace("\n", "<br>"))
            self.question_cancel.setVisible(bool(q[2]))

    def show_maps(self, items, current, preview=None):
        self.maps.show_maps(items, current)
        self.maps.show_preview(preview)

    def show_page(self, key, search=None):
        """Go to a page (e.g. the maps with a search: a scan found only the realm)."""
        if search is not None:
            self.maps.search.blockSignals(True)
            self.maps.search.setText(search)
            self.maps.search.blockSignals(False)
        keys = [k for k, _l in PAGES]
        if key in keys:
            self.nav.setCurrentRow(keys.index(key))

    def apply_theme(self, dark: bool, zoom: float):
        pal = QPalette()
        for role, colour in qt_theme.palette_roles(dark).items():
            pal.setColor(getattr(QPalette.ColorRole, role), QColor(colour))
        pal.setColor(QPalette.Disabled, QPalette.Text, QColor(qt_theme.PALETTE[bool(dark)]["fg_dis"]))
        pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(qt_theme.PALETTE[bool(dark)]["fg_dis"]))
        QApplication.setPalette(pal)
        self.setStyleSheet(qt_theme.stylesheet(dark, zoom))
        self._dark = bool(dark)
        self._nav_icons()
        try:
            hints = QApplication.styleHints()
            hints.setColorScheme(Qt.ColorScheme.Dark if dark else Qt.ColorScheme.Light)   # title bar (Qt 6.8+)
        except AttributeError:
            pass

    def show_model(self, o, thumb=None, tips=None):
        self.overview.update_page(o, thumb, tips)
        self.show_log_alert(o.log_alert)

    def show_log_alert(self, on: bool):
        """An amber dot on the log's icon while there is an error the user has not looked at."""
        if on != self._log_alert:
            self._log_alert = on
            self._nav_icons()

    def _nav_icons(self):
        """The navigation's icons in the colours of the theme: grey, the page on display in the accent colour."""
        c = qt_theme.PALETTE[self._dark]
        ratio = self.devicePixelRatioF() or 1.0
        for row, (key, _label) in enumerate(PAGES):
            alert = key == "log" and self._log_alert
            icon = QIcon()
            icon.addPixmap(nav_icon(key, c["dim"], ratio, alert), QIcon.Normal)
            icon.addPixmap(nav_icon(key, c["accent"], ratio, alert), QIcon.Selected)
            icon.addPixmap(nav_icon(key, c["fg"], ratio, alert), QIcon.Active)
            self.nav.item(row).setIcon(icon)

    def geometry_b64(self) -> str:
        return base64.b64encode(bytes(self.saveGeometry())).decode("ascii")

    def restore_b64(self, text: str) -> bool:
        try:
            return bool(text) and self.restoreGeometry(QByteArray(base64.b64decode(text)))
        except (ValueError, TypeError):
            return False

    def bring_to_front(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def hwnd(self) -> int:
        try:
            return int(self.winId())
        except (TypeError, ValueError, RuntimeError):
            return 0

    # events: only flags and post() – see the module docstring
    def closeEvent(self, e):
        if self.allow_close:
            e.accept()
        else:
            e.ignore()
            self._post("quit")

    def changeEvent(self, e):
        if e.type() == QEvent.WindowStateChange:
            minimised = bool(self.windowState() & Qt.WindowMinimized)
            if minimised and not self.minimised:
                self._post("minimised")
            self.minimised = minimised
        super().changeEvent(e)

    def moveEvent(self, e):
        self.geometry_changed = True
        super().moveEvent(e)

    def resizeEvent(self, e):
        self.geometry_changed = True
        super().resizeEvent(e)
