"""Qt control window (stage 1 of the move from Tk to Qt, setting ``ui_toolkit`` = "qt"): navigation on the left,
page "Übersicht" in Qt; the other pages still open the Tk window on the matching tab.

Threading/event-loop rule: Tk's mainloop stays the main loop and also delivers Qt's window messages on Windows.
A Qt slot can therefore run while Tcl is inside its own event loop – calling tkinter from there can kill Python
(_tkinter loses its thread state). So nothing in here touches Tk or the App: every button only calls ``post``
(→ App.events, handled in App._poll), and the App pushes its state with ``show(model)`` from its own ticks.
No modal Qt dialogs (they would stop Tk's timers).
"""
from __future__ import annotations

import base64
import sys

from PIL import Image
from PySide6.QtCore import QByteArray, QEvent, Qt
from PySide6.QtGui import QColor, QFontDatabase, QIcon, QImage, QPalette, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QProgressBar, QPushButton,
                               QScrollArea, QSizePolicy, QSlider, QStackedWidget, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from . import qt_theme
from .i18n import N_, _
from .mapimage import FONT as FIRA

# key, label, symbol; QT_PAGES are in Qt, the others open the Tk window (stages 3–4 move them)
PAGES = (("overview", N_("Übersicht"), "◉"), ("maps", "Maps", "▦"), ("overlay", N_("Overlay"), "◧"),
         ("stats", N_("Statistik"), "▤"), ("server", N_("Server"), "◎"), ("settings", N_("Einstellungen"), "⚙"),
         ("detect", N_("Erkennung"), "✦"), ("log", "Log", "☰"))
QT_PAGES = ("overview", "maps", "overlay", "settings")
THUMB_H = 170                     # px (logical) of the map picture on the overview

# Pages that mirror a Tk tab (since 1.52): every key names a Tk widget registered with App._reg; texts, values,
# enabled/shown come from it (App._qt_refresh → show_states), a click is done on it (post("act", (key, value))).
# ("card", frame key, rows) – a row is one control or ("row", [controls]); controls: ("check"|"button"|"combo"|
# "slider"|"label"|"hint", key), ("stretch",), ("link", label, tab) = open the Tk tab (not mirrored there yet).
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
            ("row", (("label", "st.zoom.label"), ("combo", "st.zoom"), ("stretch",))),
            ("check", "st.qt"),
            ("row", (("label", "st.style.label"), ("combo", "st.style"), ("stretch",))),
            ("hint", "st.look_note"))),
        ("card", "st.notify", (
            ("check", "st.lobby_notify"), ("check", "st.lobby_remind"), ("check", "st.notify_background_only"),
            ("hint", "st.notify_text"), ("row", (("button", "st.notify_test"), ("stretch",))))),
        ("card", "st.start", (("check", "st.tray"), ("check", "st.autostart"), ("hint", "st.autostart_info"))),
        ("card", "st.hotkeys", tuple(("row", (("label", f"st.hk.{k}.label"), ("stretch",), ("value", f"st.hk.{k}")))
                                     for k in ("toggle_overlay", "next_variant", "scan_now", "prev_map", "next_map",
                                               "bigger", "smaller", "edit_position", "rotate_map", "next_floor",
                                               "reject_map"))
         + (("row", (("link", N_("Hotkeys ändern …"), "settings"), ("stretch",))),)),
        ("card", "st.updates", (
            ("check", "st.update"), ("hint", "st.update_note"),
            ("row", (("button", "st.upd_btn"), ("button", "st.upd_apply"), ("stretch",))), ("hint", "st.upd_status"))),
        ("links", (("link", N_("Mehr (Map-Zuordnungen, Match-Daten, Sicherung, Ordner) …"), "settings_more"),)),
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
        elif kind in ("check", "button", "combo", "slider", "label", "hint", "value", "plain"):
            yield it[1]


def page_keys(page: str | None = None) -> set:
    """Tk widget keys a page mirrors (all pages without ``page``) – also the whitelist for clicks from Qt."""
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
    """Hover text of a Qt-only button: the same table as the Tk window (tooltip.TIPS, by German label)."""
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
        for text, action in ((N_("Zuordnen …"), "assign"), (N_("Bild hinzufügen …"), "picture")):
            ub = QPushButton(_(text))
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


def _scroll_page(title):
    """(page, body layout): a page that scrolls as a whole, with its title on top."""
    page = QWidget()
    page.setObjectName("page")
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    outer.addWidget(scroll)
    body = QWidget()
    body.setObjectName("page")
    scroll.setWidget(body)
    lay = QVBoxLayout(body)
    lay.setContentsMargins(22, 18, 22, 18)
    lay.setSpacing(12)
    lay.addWidget(_label(title, "h1"))
    return page, lay


class FormPage(QWidget):
    """A page that mirrors a Tk tab control by control (SPECS): the Tk widgets keep doing the work."""

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
        if kind == "stretch":
            lay.addStretch()
            return
        if kind == "link":
            b = QPushButton(_(item[1]))
            b.setToolTip(_tip(item[1]))
            b.clicked.connect(lambda _c=False, tab=item[2]: self._post("tab", tab))
            lay.addWidget(b)
            return
        key = item[1]
        extra = None
        if kind == "check":
            w = QCheckBox()
            w.clicked.connect(lambda checked, k=key: self._post("act", (k, checked)))
        elif kind == "button":
            w = QPushButton()
            w.clicked.connect(lambda _c=False, k=key: self._post("act", (k, None)))
        elif kind == "combo":
            w = QComboBox()
            w.setMinimumWidth(160)
            w.setSizeAdjustPolicy(QComboBox.AdjustToContents)
            w.activated.connect(lambda i, k=key, c=None: self._post("act", (k, self.controls[k][1].itemText(i))))
        elif kind == "slider":
            w = QWidget()
            r = QHBoxLayout(w)
            r.setContentsMargins(0, 0, 0, 0)
            name, value = _label(), _label()
            name.setMinimumWidth(110)
            value.setMinimumWidth(56)
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            s = QSlider(Qt.Horizontal)
            s.valueChanged.connect(lambda v, k=key: self._post("act", (k, v)))
            r.addWidget(name)
            r.addWidget(s, 1)
            r.addWidget(value)
            extra = (name, s, value)
        elif kind in ("hint", "plain"):
            w = _label(cls="dim", wrap=True)
        elif kind == "value":
            w = _label()
            w.setStyleSheet("font-weight: 600;")
        else:                              # label
            w = _label()
        lay.addWidget(w)
        self.controls[key] = (kind, w, extra)

    def show_states(self, states):
        for key, (kind, w, extra) in self.controls.items():
            st = states.get(key)
            if st is None:
                continue
            if kind != "title":
                w.setVisible(bool(st.get("visible", True)) and (kind not in ("hint", "plain") or bool(st.get("text"))))
            if "enabled" in st:
                w.setEnabled(st["enabled"])
            if st.get("tip") is not None and w.toolTip() != st["tip"]:
                w.setToolTip(st["tip"])
            if kind == "check":
                _set(w, st.get("text", ""))
                if w.isChecked() != bool(st.get("value")):
                    w.setChecked(bool(st.get("value")))         # setChecked does not emit clicked
            elif kind == "combo":
                values = st.get("values", [])
                if [w.itemText(i) for i in range(w.count())] != values:
                    w.blockSignals(True)
                    w.clear()
                    w.addItems(values)
                    w.blockSignals(False)
                if w.currentText() != st.get("value"):
                    w.blockSignals(True)
                    w.setCurrentIndex(max(0, w.findText(st.get("value", ""))))
                    w.blockSignals(False)
            elif kind == "slider":
                name, s, value = extra
                _set(name, st.get("label", ""))
                _set(value, st.get("text", ""))
                if not s.isSliderDown():                          # the user is dragging: no pull back
                    s.blockSignals(True)
                    s.setRange(round(st.get("lo", 0)), round(st.get("hi", 100)))
                    s.setValue(round(st.get("value", 0)))
                    s.blockSignals(False)
            else:                                                 # button, label, hint, value, title
                text = st.get("text", "")
                _set(w, text.upper() if kind == "title" else text)


class MapsPage(QWidget):
    """Search + list of maps (grouped by realm); double click / Enter shows a map."""

    def __init__(self, post):
        super().__init__()
        self._post = post
        page, lay = _scroll_page("Maps")
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
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumHeight(360)
        self.tree.itemActivated.connect(self._picked)
        lay.addWidget(self.tree, 1)
        lay.addWidget(_label(_("Doppelklick zeigt die Map. Die Erkennung übernimmt beim nächsten Match wieder."),
                             "dim", wrap=True))
        prow = QHBoxLayout()
        b = QPushButton(_("Kartenbild hinzufügen …"))
        b.setToolTip(_tip("Kartenbild hinzufügen …"))
        b.clicked.connect(lambda: self._post("add_picture"))
        prow.addWidget(b)
        prow.addWidget(_label(_("eigenes Bild für eine Map (Hintergrund wird entfernt)"), "dim"))
        prow.addStretch()
        lay.addLayout(prow)
        self._items = None

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
            self.tree.clear()
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


class LaterPage(QWidget):
    """A page that is not in Qt yet: says so and opens the Tk window there."""

    def __init__(self, post, key, label):
        super().__init__()
        self.setObjectName("page")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(_label(label, "h1"))
        lay.addWidget(_label(_("Diese Seite ist noch im bisherigen Fenster – sie zieht in den nächsten Versionen um. "
                               "Das Fenster wurde geöffnet."), "dim", wrap=True))
        b = QPushButton(_("Im bisherigen Fenster öffnen"))
        b.setToolTip(_tip("Im bisherigen Fenster öffnen"))
        b.clicked.connect(lambda: post("tab", key))
        lay.addWidget(b, alignment=Qt.AlignLeft)
        lay.addStretch()


class MainWindow(QMainWindow):
    def __init__(self, post, icon_path: str | None = None):
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
        self.forms = {key: FormPage(post, _(label), SPECS[key]) for key, label, _s in PAGES if key in SPECS}
        for key, label, symbol in PAGES:
            item = QListWidgetItem(f"{symbol}   {_(label)}")
            item.setData(Qt.UserRole, key)
            self.nav.addItem(item)
            page = {"overview": self.overview, "maps": self.maps}.get(key) or self.forms.get(key)
            self.stack.addWidget(page or LaterPage(post, key, _(label)))
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._page_changed)
        lay.addWidget(self.nav)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.resize(1100, 760)
        self.setMinimumSize(760, 520)
        self._log_alert = False

    def _page_changed(self, row):
        self.stack.setCurrentIndex(row)
        key = PAGES[row][0]
        self._post("page" if key in QT_PAGES else "tab", key)      # fill it now / open the Tk tab

    def current_key(self) -> str:
        return PAGES[max(0, self.nav.currentRow())][0]

    def show_states(self, page, states):
        if page in self.forms:
            self.forms[page].show_states(states)

    def show_maps(self, items, current):
        self.maps.show_maps(items, current)

    def apply_theme(self, dark: bool, zoom: float):
        pal = QPalette()
        for role, colour in qt_theme.palette_roles(dark).items():
            pal.setColor(getattr(QPalette.ColorRole, role), QColor(colour))
        pal.setColor(QPalette.Disabled, QPalette.Text, QColor(qt_theme.PALETTE[bool(dark)]["fg_dis"]))
        pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(qt_theme.PALETTE[bool(dark)]["fg_dis"]))
        QApplication.setPalette(pal)
        self.setStyleSheet(qt_theme.stylesheet(dark, zoom))
        try:
            hints = QApplication.styleHints()
            hints.setColorScheme(Qt.ColorScheme.Dark if dark else Qt.ColorScheme.Light)   # title bar (Qt 6.8+)
        except AttributeError:
            pass

    def show_model(self, o, thumb=None, tips=None):
        self.overview.update_page(o, thumb, tips)
        if o.log_alert != self._log_alert:
            self._log_alert = o.log_alert
            self.nav.item(len(PAGES) - 1).setText(f"{PAGES[-1][2]}   Log" + (" ⚠" if o.log_alert else ""))

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
