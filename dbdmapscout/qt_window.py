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
from PySide6.QtCore import QByteArray, QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFontDatabase, QIcon, QImage, QPalette, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QPlainTextEdit, QProgressBar,
                               QPushButton, QRadioButton,
                               QScrollArea, QSizePolicy, QSlider, QStackedWidget, QTabWidget, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from . import qt_theme
from .qt_layouts import FlowRow, TileGrid, WrapCheck
from .i18n import N_, _
from .mapimage import FONT as FIRA

# key, label (the navigation's icons are drawn by nav_icon: same size and place for all)
PAGES = (("overview", N_("Übersicht")), ("maps", "Maps"), ("overlay", N_("Overlay")), ("stats", N_("Statistik")),
         ("server", N_("Server")), ("settings", N_("Einstellungen")), ("detect", N_("Erkennung")), ("log", "Log"))
NAV_ICON = 18                     # px (logical): every icon of the navigation in the same box
NAV_W, NAV_COMPACT_W = 190, 62    # px (logical): navigation with names / only icons
NAV_COMPACT_BELOW = 960           # px (logical) window width from which the navigation shows only icons
AUTO_PAGES = ("stats", "server", "detect", "log")   # built from the tab's structure (app_qt.ui_layout)
THUMB_H = 170                     # px (logical) of the map picture on the overview
SETUP_W = 820                     # px (logical): widest step of the setup assistant
FOUND_MS = 1800                   # ms a search hit's card stays lit
SLIDER_MAX = 420                  # px (logical): longest slider (overlay position, size, opacity)

# Hand-made pages: every key names a widget of the UI model registered with App._reg; texts, values,
# enabled/shown come from it (App._qt_refresh → show_states), a click is done on it (post("act", (key, value))).
# ("card", frame key, rows) – a row is one control or ("row", [controls]); controls: ("check"|"button"|"combo"|
# "slider"|"label"|"hint", key), ("stretch",).
SPECS = {
    "overlay": (
        ("card", "ov.pos", (
            ("preview", "ov.preview"),
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
            ("hint", "ov.sys_text"), ("hint", "ov.sys_hint"), ("check", "ov.today"),
            ("check", "ov.media"), ("row", (("label", "ov.media_pos.label"), ("combo", "ov.media_pos"), ("stretch",))),
            ("row", (("label", "ov.media_style.label"), ("combo", "ov.media_style"), ("stretch",))),
            ("slider", "ov.media_size"), ("check", "ov.media_cover"), ("check", "ov.media_progress"))),
    ),
    "settings": (
        ("card", "st.look", (
            ("row", (("label", "st.lang.label"), ("combo", "st.lang"), ("stretch",))), ("hint", "st.lang_note"),
            ("check", "st.dark"),
            ("row", (("label", "st.theme.label"), ("combo", "st.theme"), ("stretch",))), ("swatches", "st.swatches"),
            ("check", "st.oled"),
            ("row", (("label", "st.zoom.label"), ("combo", "st.zoom"), ("stretch",))),
            ("row", (("button", "st.card_reset"), ("hint", "st.card_hint"))))),
        ("card", "st.notify", (
            ("check", "st.lobby_notify"), ("check", "st.lobby_remind"), ("check", "st.notify_background_only"),
            ("hint", "st.notify_text"), ("row", (("button", "st.notify_test"), ("stretch",))))),
        ("card", "st.start", (("check", "st.tray"), ("check", "st.autostart"), ("hint", "st.autostart_info"),
                              ("row", (("button", "st.setup_again"), ("stretch",))))),
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


# The setup assistant on the first start (1.60, user's wish): three steps of controls that are also on the pages
# (same keys – the same widgets of the UI model). ("note", text) = an explaining line of the step itself.
GAME_LANGS = ("en", "de", "fr", "es", "es-MX", "it", "pl", "pt-BR", "tr")   # app.LANGS (test: the same)
SETUP_HOTKEYS = ("toggle_overlay", "rotate_map", "edit_position", "scan_now", "reject_map")
SETUP = (
    (N_("Sprache"), (
        ("note", N_("Das Programm liest beim Match-Start den Map-Namen aus dem Bild. Hake die Sprache an, in der "
                    "du Dead by Daylight spielst (mehrere gehen).")),
        ("grid", 5, tuple(("check", f"det.lang.{code}") for code in GAME_LANGS)),
        ("note", N_("Sprache dieses Programms:")),
        ("row", (("combo", "st.lang"), ("stretch",))), ("hint", "st.lang_note"))),
    (N_("Overlay"), (
        ("note", N_("Die Karte erscheint beim Match-Start von selbst und verschwindet nach der Runde. „automatisch“ "
                    "legt sie in den schwarzen Rand neben dem Spielbild (Ultrawide) bzw. neben das DBD-Fenster.")),
        ("row", (("label", "ov.anchor.label"), ("combo", "ov.anchor"), ("stretch",))),
        ("slider", "ov.size"),
        ("row", (("button", "ov.test"), ("button", "ov.edit"), ("stretch",))),
        ("note", N_("„Overlay testen“ zeigt die Karte sofort, „Mit der Maus verschieben“ lässt sie dich hinziehen.")))),
    (N_("Tasten und Start"), (
        ("note", N_("Die wichtigsten Tasten – zum Ändern draufklicken und die neue Kombination drücken. Alle "
                    "Tasten findest du später unter Einstellungen.")),
        ("grid", 1, tuple(("row", (("label", f"st.hk.{k}.label"), ("stretch",), ("hotkey", f"st.hk.{k}")))
                          for k in SETUP_HOTKEYS)),
        ("check", "st.autostart"), ("check", "st.lobby_notify"))),
)


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
        elif kind in ("check", "button", "combo", "slider", "label", "hint", "value", "plain", "hotkey", "preview",
                      "swatches"):
            yield it[1]


def page_keys(page: str | None = None) -> set:
    """Widget keys a hand-made page shows (all pages without ``page``) – also the whitelist for its clicks."""
    if page == "setup":
        return {k for _t, items in SETUP for k in _spec_keys(items)}
    pages = [page] if page else list(SPECS) + ["setup"]
    return {k for p in pages for k in (page_keys("setup") if p == "setup" else _spec_keys(SPECS.get(p, ())))}


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

        top = FlowRow(spacing=12)                 # narrow window: the status goes below the title
        top.right = 1
        top.addWidget(_label(_("Übersicht"), "h1"))
        self.pill = QLabel()
        self.pill.setObjectName("pill")
        self.pill.setMaximumWidth(520)
        top.addWidget(self.pill)
        page.addLayout(top)

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
        grid = TileGrid(min_width=110, columns=4, spacing=20)    # four values side by side, or two by two
        self.facts = [FactBox() for _i in range(4)]
        for box in self.facts:
            grid.addWidget(box)
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
        btns = FlowRow(spacing=6)                 # the buttons wrap instead of running out of the card
        self.buttons = {}
        for key in ("scan", "rotate", "toggle", "reject", "confirm", "layout", "floor"):
            b = QPushButton()
            if key == "scan":
                b.setObjectName("primary")
            b.clicked.connect(lambda _c=False, k=key: self._post(k))
            btns.addWidget(b)
            self.buttons[key] = b
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
        tiles = TileGrid(min_width=170, columns=4)
        self.tiles = []
        for _i in range(4):
            t = _card()
            tl = QVBoxLayout(t)
            tl.setContentsMargins(14, 12, 14, 12)
            box = FactBox(bar=True)
            box.sub.setWordWrap(True)
            tl.addWidget(box)
            tiles.addWidget(t)
            self.tiles.append(box)
        page.addLayout(tiles)

        # system values and the last rounds
        row = TileGrid(min_width=300, columns=2)  # side by side, below each other in a narrow window
        sysc = _card()
        self.sys_lay = QVBoxLayout(sysc)
        self.sys_lay.setContentsMargins(14, 12, 14, 12)
        self.sys_lay.addWidget(_label(_("System").upper(), "h2"))
        self.sys_rows = []
        self.sys_note = _label(cls="dim", wrap=True)
        self.sys_lay.addWidget(self.sys_note)
        self.sys_lay.addStretch()
        row.addWidget(sysc)
        last = _card()
        self.last_lay = QVBoxLayout(last)
        self.last_lay.setContentsMargins(14, 12, 14, 12)
        self.last_lay.addWidget(_label(_("Letzte Runden").upper(), "h2"))
        self.last_rows = []
        self.last_empty = _label(_("Noch keine Runden gespeichert."), "dim")
        self.last_lay.addWidget(self.last_empty)
        self.last_lay.addStretch()
        row.addWidget(last)
        page.addLayout(row)
        page.addStretch()

    # ------------------------------------------------------------- update
    def update_page(self, o, thumb=None, tips=None):
        _set(self.pill, "●  " + o.status_text)
        pill = qt_theme.pill_style(o.status_kind)
        if pill != self._pill_style:                  # re-styling repaints: only on a change
            self._pill_style = pill
            self.pill.setStyleSheet(pill)
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
        w = WrapCheck()                           # its text wraps in a narrow window (QCheckBox's does not)
        w.clicked.connect(lambda checked: post("act", (key, checked)))
    elif kind == "button":
        w = QPushButton()
        # Tab only, no focus by click (1.62.2): a button that disables itself on click passed its focus on and
        # the page scrolled to whatever came next in the tab order
        w.setFocusPolicy(Qt.TabFocus)
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
    elif kind == "tiles":
        w = TilesView()
    elif kind == "preview":
        w = PreviewView(key, post)
    elif kind == "swatches":
        w = SwatchView(key, post)
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
    elif kind in ("table", "chart", "log", "dashboard", "tiles", "preview", "swatches"):
        w.show_state(st)
    elif kind == "hotkey":
        w.show_text(st.get("text", ""))
        w.show_recording(bool(st.get("recording")))
    elif kind in ("box", "card"):
        pass
    else:                                                         # button, label, hint, value, title, big
        text = st.get("text", "")
        _set(w, text.upper() if kind == "title" else text)


class Grip(QWidget):
    """The handle at the right of a card's title: six dots; dragging it moves the card (CardColumn)."""

    def __init__(self, column, card):
        super().__init__()
        self._column, self._card = column, card
        self.setFixedSize(16, 18)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip(_("Ziehen, um den Kasten zu verschieben"))

    def paintEvent(self, _e):
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(self.palette().color(QPalette.PlaceholderText))
        for x in (5, 11):
            for y in (4, 9, 14):
                p.drawEllipse(x - 1.5, y - 1.5, 3, 3)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.setCursor(Qt.ClosedHandCursor)
            self._column.begin(self._card)

    def mouseMoveEvent(self, e):
        self._column.drag_to(e.globalPosition().toPoint())

    def mouseReleaseEvent(self, _e):
        self.setCursor(Qt.OpenHandCursor)
        self._column.end()


class CardColumn(QWidget):
    """Cards below each other that the user can put in their own order (1.59, user's wish: "Updates nach oben
    schieben"): drag a card at its grip, the others make room as it passes them; the page scrolls at its edges.
    No QDrag – that runs a second event loop. ``on_order(ids)`` gets the new order (saved by the App)."""

    def __init__(self, on_order=None):
        super().__init__()
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(12)
        self.cards = []                   # [(id, card)] in the order shown
        self._default = []
        self._drag = None
        self._before = None
        self.on_order = on_order
        self._scroll = None
        self._timer = QTimer(self)        # scrolls the page while the card is held at its top/bottom edge
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._autoscroll)

    def add(self, card_id, card, head_row):
        """``head_row``: the card's title layout – the grip goes to its right end."""
        head_row.addWidget(Grip(self, card), 0, Qt.AlignVCenter)
        self.cards.append((card_id, card))
        self._default.append(card_id)
        self._lay.addWidget(card)

    def ids(self) -> list:
        return [i for i, _c in self.cards]

    def apply(self, ids):
        """Show the cards in this order; ids it does not know, or a missing card (another version), = default."""
        if not ids or sorted(ids) != sorted(self._default):
            ids = self._default
        if ids == self.ids():
            return
        by_id = dict(self.cards)
        for _i, card in self.cards:
            self._lay.removeWidget(card)
        self.cards = [(i, by_id[i]) for i in ids]
        for _i, card in self.cards:
            self._lay.addWidget(card)
        self._tab_order()

    def _tab_order(self):
        """Tab order = the order shown (1.62.2): Qt keeps the order the widgets were made in. A button that
        disables itself on click ("Jetzt nach Updates suchen") hands its focus to the next one in that chain –
        a card that now sits far below – and the page scrolled down to it."""
        def focusable(card):
            return [w for w in card.findChildren(QWidget) if w.focusPolicy() & Qt.TabFocus]
        widgets = [w for _i, card in self.cards for w in focusable(card)]
        if len(widgets) < 2:
            return
        inside = set(map(id, widgets))
        by_id = dict(self.cards)
        first = next((w for i in self._default for w in focusable(by_id[i])), None)
        prev = first.previousInFocusChain() if first is not None else None
        while prev is not None and id(prev) in inside:
            prev = prev.previousInFocusChain()
        chain = ([prev] if prev is not None else []) + widgets
        for a, b in zip(chain, chain[1:]):
            QWidget.setTabOrder(a, b)

    def begin(self, card):
        self._drag = card
        self._before = self.ids()
        card.setProperty("dragging", True)
        card.style().unpolish(card)
        card.style().polish(card)
        w = self.parentWidget()
        while w is not None and not isinstance(w, QScrollArea):
            w = w.parentWidget()
        self._scroll = w
        self._timer.start()

    def drag_to(self, global_pos):
        card = self._drag
        if card is None:
            return
        y = self.mapFromGlobal(global_pos).y()
        others = [(i, c) for i, c in self.cards if c is not card]
        pos = len(others)
        for n, (_i, c) in enumerate(others):
            if c.isVisible() and y < c.geometry().center().y():
                pos = n
                break
        me = next(e for e in self.cards if e[1] is card)
        if self.cards.index(me) != pos:
            others.insert(pos, me)
            self.cards = others
            self._lay.removeWidget(card)
            self._lay.insertWidget(pos, card)

    def _autoscroll(self):
        from PySide6.QtGui import QCursor
        sa = self._scroll
        if self._drag is None or sa is None:
            return
        y = sa.viewport().mapFromGlobal(QCursor.pos()).y()
        h = sa.viewport().height()
        step = -18 if y < 40 else 18 if y > h - 40 else 0
        if step:
            bar = sa.verticalScrollBar()
            bar.setValue(bar.value() + step)
            self.drag_to(QCursor.pos())

    def end(self):
        card, self._drag = self._drag, None
        self._timer.stop()
        if card is None:
            return
        card.setProperty("dragging", False)
        card.style().unpolish(card)
        card.style().polish(card)
        if self.ids() != self._before:
            self._tab_order()
            if self.on_order is not None:
                self.on_order(self.ids())


def _card_head(card_layout):
    """Title row of a card: (title label, row) – CardColumn puts its grip at the end of the row."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    head = _label(cls="h2")
    row.addWidget(head, 1)
    card_layout.addLayout(row)
    return head, row


class _Arranged:
    """Pages whose cards the user can put in order: one CardColumn per run of cards (a run ends at anything
    else, e.g. Settings' "Mehr" button). ``post("card_order", (page, run, ids))`` saves; ``apply_order``."""

    def _column(self, page_key):
        n = len(self.columns)
        col = CardColumn(lambda ids, n=n: self._post("card_order", (page_key, n, ids)))
        self.columns.append(col)
        return col

    def apply_order(self, saved: dict):
        for n, col in enumerate(self.columns):
            col.apply((saved or {}).get(str(n)))


class FormPage(QWidget, _Arranged):
    """A hand-made page (SPECS): one control per widget of the UI model, which does the work."""

    def __init__(self, post, title, spec, page_key=""):
        super().__init__()
        self._post = post
        self.controls = {}                 # key -> (kind, widget, extra)
        self.columns = []
        page, lay = _scroll_page(title)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        col = None
        for item in spec:
            kind = item[0]
            if kind != "card":
                col = None
            if kind == "card":
                if col is None:
                    col = self._column(page_key)
                    lay.addWidget(col)
                card = _card()
                cl = QVBoxLayout(card)
                cl.setContentsMargins(14, 12, 14, 12)
                cl.setSpacing(6)
                head, hrow = _card_head(cl)
                self.controls[item[1]] = ("title", head, None)
                for row in item[2]:
                    self._add(row, cl)
                col.add(item[1], card, hrow)
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
            kids = item[1]
            if any(c[0] in ("hint", "slider") for c in kids):    # text that wraps beside controls: a plain row
                row = QHBoxLayout()
                row.setSpacing(8)
                for c in kids:
                    self._add(c, row)
            else:                                     # controls only: they wrap when the window is narrow
                row = FlowRow()
                cut = next((i for i, c in enumerate(kids) if c[0] == "stretch"), len(kids))
                row.right = len([c for c in kids[cut:] if c[0] != "stretch"])
                for c in kids:
                    if c[0] != "stretch":
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
        if kind == "note":                          # a fixed text of the page itself (setup assistant)
            lay.addWidget(_label(_(item[1]), wrap=True))
            return
        w, extra = make_control(kind, item[1], self._post)
        if isinstance(lay, FlowRow):
            lay.addWidget(w)
        else:
            lay.addWidget(w, 1 if kind == "hint" and isinstance(lay, QHBoxLayout) else 0)  # text beside: takes the room
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
        c = qt_theme.colours(self._dark)
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
        c = qt_theme.colours(self._dark)
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


class SwatchView(QWidget):
    """The colour palette below the theme list (1.63, user's wish): one square per colour, the chosen one ringed,
    and "Eigene Farbe …" with Qt's colour dialog (non-modal, no second event loop). post("act", (key, "#rrggbb"))
    – qt_theme.derive_accent makes any colour readable."""

    SIZE = 22

    def __init__(self, key, post):
        super().__init__()
        self._key, self._post = key, post
        self._values, self._current = (), None
        self._buttons = []
        self._dialog = None
        self._row = FlowRow(self, spacing=6)
        self.own = QPushButton(_("Eigene Farbe …"))
        self.own.setFocusPolicy(Qt.TabFocus)
        self.own.setToolTip(_("Beliebige Farbe wählen – das Programm passt die Helligkeit an, bis alles lesbar "
                              "ist."))
        self.own.clicked.connect(self._pick)
        self._row.addWidget(self.own)

    def show_state(self, st):
        values = tuple(st.get("values") or ())
        current = (st.get("current"), bool(st.get("dark", True)))
        if values != self._values:
            for b in self._buttons:
                self._row.removeWidget(b)
                b.deleteLater()
            self._buttons = []
            self._row.removeWidget(self.own)
            for colour, tip in values:
                b = QPushButton()
                b.setFixedSize(self.SIZE, self.SIZE)
                b.setFocusPolicy(Qt.TabFocus)
                b.setCursor(Qt.PointingHandCursor)
                b.setToolTip(tip)
                b.setProperty("swatch", colour)
                b.clicked.connect(lambda _c=False, v=colour: self._post("act", (self._key, v)))
                self._row.addWidget(b)
                self._buttons.append(b)
            self._row.addWidget(self.own)
            self._values, self._current = values, object()
        if current != self._current:
            self._current = current
            chosen, dark = current
            for b in self._buttons:
                colour = b.property("swatch")
                ring = qt_theme.colours(dark)["fg"] if colour == chosen else "transparent"
                b.setStyleSheet(f"QPushButton {{ background: {colour}; border: 2px solid {ring}; "
                                f"border-radius: 4px; padding: 0; min-width: 0; }}")
                b.setAccessibleName(colour)

    def _pick(self):
        from PySide6.QtWidgets import QColorDialog
        chosen = self._current[0] if isinstance(self._current, tuple) else None
        dlg = QColorDialog(QColor(chosen or qt_theme.CUSTOM_DEFAULT), self.window())
        dlg.setOption(QColorDialog.DontUseNativeDialog, True)
        dlg.setWindowTitle(_("Eigene Farbe"))
        dlg.colorSelected.connect(lambda c: self._post("act", (self._key, c.name())))
        dlg.open()
        self._dialog = dlg                       # keep it alive while it is open


PREVIEW_NAMES = {"map": N_("Karte"), "hud": N_("Systemwerte"), "music": N_("Musik")}


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
        self.setMouseTracking(True)            # open hand over an element
        sp = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)
        self.setMinimumHeight(120)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(_("Erst „Mit der Maus verschieben“ drücken, dann Karte, Systemwerte oder Musik anfassen "
                          "und ziehen – oder auf eine freie Stelle klicken: Die Karte kommt dorthin. Ende mit "
                          "„Fertig“."))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        sw, sh = self._data.get("screen") or (16, 9)
        return min(self.MAX_H, max(120, round(w * sh / max(1, sw))))

    def sizeHint(self):
        return QSize(560, self.heightForWidth(560))

    def show_state(self, st):
        data = st.get("data") or {}
        key = {k: v for k, v in data.items() if k != "pics"}
        old = {k: v for k, v in self._data.items() if k != "pics"}
        pics, old_pics = data.get("pics") or {}, self._data.get("pics") or {}
        if key == old and pics.keys() == old_pics.keys() and all(pics[k] is old_pics[k] for k in pics):
            return
        shape = data.get("screen") != self._data.get("screen")
        self._data = data
        if shape:
            self.updateGeometry()
        self.update()

    def _frame(self):
        """(left, top, scale): where the screen is drawn in the widget, screen px -> widget px."""
        sw, sh = self._data.get("screen") or (16, 9)
        s = min(self.width() / max(1, sw), self.height() / max(1, sh))
        return (self.width() - sw * s) / 2, (self.height() - sh * s) / 2, s

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
        p.drawText(game, Qt.AlignCenter, _("Spielbild"))
        # every element as the game shows it (1.64): map + lines, system values, music card – real pictures
        pics = d.get("pics") or {}
        ratio = self.devicePixelRatioF()
        cache = self._pix if isinstance(self._pix, dict) else {}
        fresh = {}
        p.setOpacity(float(d.get("opacity", 1.0)))
        for name, lx, ly, lw, lh in d.get("layers") or ():
            img = pics.get(name)
            if img is None:
                continue
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
            p.drawText(game.adjusted(0, 6, 0, 0), Qt.AlignHCenter | Qt.AlignTop,
                       _("Verschieben aktiv – Elemente ziehen, dann „Fertig“"))
        if d.get("editing"):                       # every element named; the one under the mouse in accent colour
            accent = QColor(qt_theme.colours(True)["accent"])
            held = self._grab[0] if self._grab else self._hover
            tf = QFont(self.font())
            tf.setBold(True)
            tf.setPixelSize(11)
            p.setFont(tf)
            for name, lx, ly, lw, lh in d.get("layers") or ():
                r = QRectF(ox + lx * s, oy + ly * s, lw * s, lh * s)
                on = name == held
                p.setPen(QPen(accent if on else QColor(255, 255, 255, 140), 2 if on else 1,
                              Qt.SolidLine if on else Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawRect(r)
                tag = _(PREVIEW_NAMES.get(name, name))
                tw = p.fontMetrics().horizontalAdvance(tag) + 8
                tr = QRectF(max(screen.left(), min(r.left(), screen.right() - tw)), max(oy, r.top() - 15), tw, 15)
                p.fillRect(tr, accent if on else QColor(30, 30, 34, 220))
                p.setPen(QColor(20, 16, 4) if on else QColor(235, 235, 235))
                p.drawText(tr, Qt.AlignCenter, tag)
            if held:
                p.setPen(accent)
                p.setFont(tf)
                what = _("Ziehst: {name}", name=_(PREVIEW_NAMES.get(held, held))) if self._grab else \
                    _("Unter der Maus: {name}", name=_(PREVIEW_NAMES.get(held, held)))
                p.drawText(game.adjusted(0, 0, 0, -6), Qt.AlignHCenter | Qt.AlignBottom, what)
        x, y, w, h, _mh = d.get("rect") or (0, 0, 0, 0, 0)
        if w and h and not d.get("editing"):
            rx, ry = ox + x * s, oy + y * s
            pen = QPen(QColor(qt_theme.colours(True)["accent"]), 1.5, Qt.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(rx, ry, w * s, h * s))
        p.end()

    def _screen_pos(self, e):
        ox, oy, s = self._frame()
        pos = e.position()
        return ((pos.x() - ox) / s, (pos.y() - oy) / s) if s > 0 else None

    def layer_at(self, x, y):
        """(name, dx, dy) of the topmost element under screen point (x, y), or None (1.64.1)."""
        for name, lx, ly, lw, lh in reversed(self._data.get("layers") or ()):
            if lx <= x <= lx + lw and ly <= y <= ly + lh:
                return name, x - lx, y - ly
        return None

    def _move(self, e):
        pt = self._screen_pos(e)
        if pt is None:
            return
        if self._grab:                     # an element held at the place it was grabbed: its corner follows
            name, dx, dy = self._grab
            self._post("act", (self._key, ("place", name, pt[0] - dx, pt[1] - dy)))
        else:                              # empty place: the map's centre goes there
            self._post("act", (self._key, ("move", pt[0], pt[1])))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self._data.get("editing"):
            pt = self._screen_pos(e)
            self._grab = self.layer_at(*pt) if pt else None
            self._dragging = True
            self.setCursor(Qt.ClosedHandCursor)
            if not self._grab:
                self._move(e)

    def mouseMoveEvent(self, e):
        if self._dragging:
            self._move(e)
        elif not self._data.get("editing"):
            self.setCursor(Qt.ArrowCursor)
        else:
            pt = self._screen_pos(e)
            hit = self.layer_at(*pt) if pt else None
            self.setCursor(Qt.OpenHandCursor if hit else Qt.PointingHandCursor)
            if (hit[0] if hit else None) != self._hover:
                self._hover = hit[0] if hit else None
                self.update()

    def leaveEvent(self, _e):
        if self._hover:
            self._hover = None
            self.update()

    def mouseReleaseEvent(self, _e):
        self._dragging = False
        self._grab = None
        self.setCursor(Qt.PointingHandCursor)


class TilesView(QWidget):
    """Key figure tiles (uimodel.Tiles): as many side by side as fit (TileGrid), each a FactBox on a card."""

    def __init__(self):
        super().__init__()
        self._grid = TileGrid(self, min_width=150, columns=6)
        self._tiles = []
        self._shown = None

    def show_state(self, st):
        data = st.get("data") or []
        if data is self._shown:
            return
        self._shown = data
        while len(self._tiles) < len(data):
            card = _card()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            box = FactBox(bar=True)
            box.sub.setWordWrap(True)
            cl.addWidget(box)
            self._grid.addWidget(card)
            self._tiles.append((card, box))
        for i, (card, box) in enumerate(self._tiles):
            card.setVisible(i < len(data))
            if i < len(data):
                box.show_fact(data[i])
        self.setVisible(bool(data))


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
        self.grid = TileGrid(self.tiles_box, min_width=140, columns=6)   # fewer columns in a narrow window
        self.tiles = []
        for _i in range(6):
            card = _card()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            box = FactBox(bar=True)
            box.sub.setWordWrap(True)                 # "no killer rounds with stats data": wraps in a narrow window
            cl.addWidget(box)
            self.grid.addWidget(card)
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


FLOW_KINDS = ("button", "combo", "check", "radio", "label", "entry", "value", "big")   # rows of these may wrap


def _grows(node) -> bool:
    """A table, chart or the log below this node: it may take the free height of the page."""
    return (node.get("kind") in ("table", "chart", "log") and not node.get("fit")) or \
        any(_grows(c) for c in node.get("children", ()))


def _fills(node) -> bool:
    """A notebook below this node fills the page (packed with expand): the page does not scroll as a whole."""
    return (node.get("kind") == "tabs" and bool(node.get("fill"))) or any(_fills(c) for c in node.get("children", ()))


class AutoPage(QWidget, _Arranged):
    """A page built from the structure of a tab of the UI model (app_qt.ui_layout): frames → cards/rows,
    notebooks → tabs, tables, charts and controls like FormPage (Statistik, Server, Erkennung, Log, dialogs)."""

    def __init__(self, post, title, node, page_key=""):
        super().__init__()
        self._post = post
        self._page_key = page_key
        self.controls = {}                 # key -> (kind, widget, extra)
        self._tabs = []                    # (QTabWidget, [keys of each page])
        self._all = []
        self.columns = []
        fill = _fills(node) if node else False
        page, lay = _scroll_page(title, scroll=not fill)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        if node:
            self._build(node, lay, self._all, top=True)
        if not fill:
            lay.addStretch()

    def _build(self, n, lay, keys, top=False, column=None):
        kind, key = n["kind"], n["key"]
        keys.append(key)
        if kind in ("box", "card"):
            holder = _card() if kind == "card" else QWidget()
            v = QVBoxLayout(holder)
            v.setContentsMargins(*((14, 12, 14, 12) if kind == "card" else (0, 0, 0, 0)))
            v.setSpacing(6)
            if kind == "card":
                head, hrow = _card_head(v)
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
                if column is not None:
                    column[0].add(column[1], holder, hrow)
                else:
                    lay.addWidget(holder, 1 if top and _grows(n) else 0)
                self.controls[key] = (kind, holder, None)
                return
            first = [c for c in kids if c.get("side") != "right"]
            last = list(reversed([c for c in kids if c.get("side") == "right"]))
            flow = n.get("row") and all(c["kind"] in FLOW_KINDS for c in kids)   # controls only: they wrap
            inner = (FlowRow() if flow else QHBoxLayout()) if n.get("row") else v
            if inner is not v:
                inner.setSpacing(8)
                v.addLayout(inner)
                if flow:
                    inner.right = len(last)
            arrange = bool(self._page_key) and top and kind == "box" and inner is v and not _grows(n)  # own order
            col, run = None, 0
            for c in first:
                if arrange and c["kind"] == "card":
                    if col is None:
                        col, run = self._column(self._page_key), 0
                        v.addWidget(col)
                    self._build(c, v, keys, column=(col, f"#{run}"))
                    run += 1
                    continue
                col = None
                self._build(c, inner, keys, top=top and inner is v)    # a table further down still gets the height
            if n.get("row") and not flow:
                inner.addStretch()
            for c in last:
                self._build(c, inner, keys, top=top and inner is v)
            if column is not None:
                column[0].add(column[1], holder, hrow)
            else:
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
        if isinstance(lay, FlowRow):
            lay.addWidget(w)
        elif kind in ("button", "combo") and not isinstance(lay, QHBoxLayout):
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
    elif key == "search":                      # magnifier
        p.drawEllipse(QPointF(c - 1.5, c - 1.5), 5.0, 5.0)
        p.drawLine(QPointF(c + 2.2, c + 2.2), QPointF(size - m, size - m))
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


class SetupPage(QWidget):
    """The setup assistant (first start, or "Einrichtung starten" in the settings): SETUP's steps one at a time,
    "Zurück" / "Weiter" / "Fertig" and "Überspringen". Done or skipped: post("setup_done")."""

    def __init__(self, post):
        super().__init__()
        self.setObjectName("page")
        self._post = post
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.steps = QStackedWidget()
        self.pages = [FormPage(post, _("Einrichtung: {step}", step=_(title)), items) for title, items in SETUP]
        for page in self.pages:
            page.setMaximumWidth(SETUP_W)               # a wide window: the keys stay next to their names
            self.steps.addWidget(page)
        lay.addWidget(self.steps, 1)
        foot = QHBoxLayout()
        foot.setContentsMargins(22, 10, 22, 16)
        self.skip = QPushButton(_("Überspringen"))
        self.skip.clicked.connect(lambda: self._post("setup_done"))
        self.where = _label(cls="dim")
        self.back = QPushButton(_("Zurück"))
        self.back.clicked.connect(lambda: self.go(self.steps.currentIndex() - 1))
        self.next = QPushButton()
        self.next.setObjectName("primary")
        self.next.clicked.connect(self._next)
        foot.addWidget(self.skip)
        foot.addStretch()
        foot.addWidget(self.where)
        foot.addSpacing(12)
        foot.addWidget(self.back)
        foot.addWidget(self.next)
        lay.addLayout(foot)
        self.go(0)

    def go(self, i: int):
        i = max(0, min(len(self.pages) - 1, i))
        self.steps.setCurrentIndex(i)
        _set(self.where, _("Schritt {n} von {total}", n=i + 1, total=len(self.pages)))
        self.back.setEnabled(i > 0)
        _set(self.next, _("Fertig") if i == len(self.pages) - 1 else _("Weiter"))

    def _next(self):
        if self.steps.currentIndex() == len(self.pages) - 1:
            self._post("setup_done")
        else:
            self.go(self.steps.currentIndex() + 1)

    def show_states(self, states):
        for page in self.pages:
            page.show_states(states)


SEARCH_KINDS = ("check", "radio", "button", "title", "label", "slider")   # what the search finds on a page


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
        self.nav.setFixedWidth(NAV_W)
        self._nav_compact = False
        self._nav_kept = False
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.stack = QStackedWidget()
        self.overview = OverviewPage(post)
        self.maps = MapsPage(post)
        self.forms = {key: FormPage(post, _(label), SPECS[key], key) for key, label in PAGES if key in SPECS}
        for key, label in PAGES:
            if key in AUTO_PAGES and (layouts or {}).get(key):
                self.forms[key] = AutoPage(post, _(label), layouts[key], key)
        self.nav.setIconSize(QSize(NAV_ICON, NAV_ICON))
        for key, label in PAGES:
            item = QListWidgetItem(_(label))
            item.setData(Qt.UserRole, key)
            self.nav.addItem(item)
            page = {"overview": self.overview, "maps": self.maps}.get(key) or self.forms.get(key) or QWidget()
            self.stack.addWidget(page)
        self.setup = SetupPage(post)
        self.stack.addWidget(self.setup)
        self._setup_on = False
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._page_changed)
        # search over the settings of all pages (1.60): a field above the navigation, Ctrl+F
        side = QWidget()
        side.setObjectName("navside")
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)
        self.search = QLineEdit()
        self.search.setObjectName("navsearch")
        self.search.setPlaceholderText(_("Einstellung suchen …"))
        self.search.setClearButtonEnabled(True)
        self.search.setFocusPolicy(Qt.ClickFocus)  # not the window's first focus: only by a click or Ctrl+F
        self.search_btn = QPushButton()
        self.search_btn.setObjectName("navsearchbtn")
        self.search_btn.setToolTip(_("Einstellung suchen (Strg+F)"))
        self.search_btn.clicked.connect(self.focus_search)
        self.search_btn.hide()
        sl.addWidget(self.search)
        sl.addWidget(self.search_btn)
        sl.addWidget(self.nav, 1)
        self._found = {}                  # completer text -> (page key, widget)
        from PySide6.QtCore import QStringListModel
        from PySide6.QtWidgets import QCompleter
        self._search_model = QStringListModel()
        self.completer = QCompleter(self._search_model, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setMaxVisibleItems(12)
        self.completer.activated.connect(self.go_to_found)
        self.search.setCompleter(self.completer)
        self.search.installEventFilter(self)
        self.search.returnPressed.connect(self._search_first)
        from PySide6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence.Find, self, activated=self.focus_search)
        lay.addWidget(side)
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
        self.setMinimumSize(560, 480)            # narrower: the navigation shows only icons, the pages wrap
        self._log_alert = False
        self._dark = True
        self._nav_icons()
        self.dialogs = {}                 # dialog path (UI model) -> DialogWindow

    def _page_changed(self, row):
        self._setup_on = False                                     # the navigation leaves the assistant
        self.stack.setCurrentIndex(row)
        self._post("page", PAGES[row][0])                          # the App fills it now

    def current_key(self) -> str:
        return "setup" if self._setup_on else PAGES[max(0, self.nav.currentRow())][0]

    def show_setup(self, on: bool = True):
        """The setup assistant instead of a page (first start); the navigation still leads away from it."""
        self._setup_on = bool(on)
        if on:
            self.setup.go(0)
            self.stack.setCurrentWidget(self.setup)
        else:
            self.stack.setCurrentIndex(max(0, self.nav.currentRow()))

    # ------------------------------------------------------------- search over the settings
    def search_index(self) -> dict:
        """{shown text: (page key, widget)} – every tick box, button, slider, card title and label the pages show
        now (folded parts like "Mehr" only once they are open)."""
        out = {}
        labels = dict(PAGES)
        for key, page in self.forms.items():
            for ckey, (kind, w, extra) in page.controls.items():
                if kind not in SEARCH_KINDS:
                    continue
                target = extra[0] if kind == "slider" else w
                text = " ".join(target.text().split())
                if len(text) < 3 or not w.isVisibleTo(page) or text.startswith("▸"):
                    continue
                entry = f"{text}  ·  {_(labels[key])}"
                out.setdefault(entry, (key, w))
        return out

    def eventFilter(self, obj, e):
        if obj is self.search and e.type() == QEvent.FocusIn:
            self._post("search_open")             # the App fills every page once (texts come from the model)
        return super().eventFilter(obj, e)

    def update_search_index(self):
        """After the App filled the pages: what the search offers (open parts, the language now …)."""
        self._found = self.search_index()
        self._search_model.setStringList(sorted(self._found, key=str.lower))

    def focus_search(self):
        if self._nav_compact:
            self._compact_nav(False, keep=True)                    # room for the field while searching
        self.search.setFocus()
        self.search.selectAll()

    def _search_first(self):
        if self.completer.completionCount():
            self.go_to_found(self.completer.currentCompletion())

    def go_to_found(self, entry: str):
        """Open the page of a search hit, scroll to it and light up its card for a moment."""
        hit = self._found.get(entry)
        if hit is None:
            return
        key, w = hit
        self.show_page(key)
        self.search.clear()
        self.search.clearFocus()
        if self._nav_kept:
            self._nav_kept = False
            self._compact_nav(self.width() < NAV_COMPACT_BELOW)

        def scroll():
            sa = w.parentWidget()
            while sa is not None and not isinstance(sa, QScrollArea):
                sa = sa.parentWidget()
            if sa is not None:
                sa.ensureWidgetVisible(w, 0, 120)
            card = w
            while card is not None and card.property("class") != "card":
                card = card.parentWidget()
            target = card or w
            target.setProperty("found", True)
            target.style().unpolish(target)
            target.style().polish(target)

            def done():
                target.setProperty("found", False)
                target.style().unpolish(target)
                target.style().polish(target)
            QTimer.singleShot(FOUND_MS, done)
        QTimer.singleShot(0, scroll)

    def show_states(self, page, states):
        if page == "setup":
            self.setup.show_states(states)
        elif page in self.forms:
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

    def set_card_order(self, orders: dict):
        """The user's order of the cards ({page: {run: [ids]}}, setting card_order); {} = as built."""
        for key, page in self.forms.items():
            page.apply_order((orders or {}).get(key, {}))

    def show_maps(self, items, current, preview=None):
        self.maps.show_maps(items, current)
        self.maps.show_preview(preview)

    def show_page(self, key, search=None):
        """Go to a page (e.g. the maps with a search: a scan found only the realm)."""
        if self._setup_on:
            self.show_setup(False)
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
        pal.setColor(QPalette.Disabled, QPalette.Text, QColor(qt_theme.colours(dark)["fg_dis"]))
        pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(qt_theme.colours(dark)["fg_dis"]))
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
        c = qt_theme.colours(self._dark)
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
        self._compact_nav(self.width() < NAV_COMPACT_BELOW)

    def _compact_nav(self, on: bool, keep: bool = False):
        """A narrow window: the navigation shows only its icons (names as hover text) – the page gets the room.
        ``keep``: opened for a search (Ctrl+F) – stays open until a hit is chosen."""
        if keep:
            self._nav_kept = True
        elif self._nav_kept:
            return
        if on == self._nav_compact:
            return
        self._nav_compact = on
        self.search.setVisible(not on)
        self.search_btn.setVisible(on)
        if on:
            self.search_btn.setIcon(QIcon(nav_icon("search", qt_theme.colours(self._dark)["dim"],
                                                   self.devicePixelRatioF() or 1.0)))
        self.nav.setFixedWidth(NAV_COMPACT_W if on else NAV_W)
        self.search.setFixedWidth(NAV_W)
        self.search_btn.setFixedWidth(NAV_COMPACT_W)
        for row, (_key, label) in enumerate(PAGES):
            item = self.nav.item(row)
            item.setText("" if on else _(label))
            item.setToolTip(_(label) if on else "")
